"""考试服务（支持后台生成、即时复习、状态流转）"""
from sqlmodel import Session, select, func, desc
from app.models import UserWordItem, WordBook, User, WordCollection, Exam, ExamSpellingSection, ExamTranslationSection, Message
from sqlalchemy import func
from app.services.llm_service import get_llm_service_for_user
from app.services.message_service import MessageService
from typing import List, Dict, Any, Optional
import uuid as uuid_pkg
import random
from datetime import datetime

class ExamService:
    @staticmethod
    def create_exam_record(
        user_id: uuid_pkg.UUID,
        collection_id: uuid_pkg.UUID,
        mode: str,
        count: int,
        session: Session
    ) -> Exam:
        """创建初始考试记录 (Pending状态)"""
        exam = Exam(
            user_id=user_id,
            collection_id=collection_id,
            mode=mode,
            exam_status="pending",
            total_words=count,
            spelling_words_count=count, # 初始预估，生成后会更新准确值
            translation_sentences_count=0
        )
        session.add(exam)
        session.commit()
        session.refresh(exam)
        return exam

    @staticmethod
    def check_review_availability(user_id: uuid_pkg.UUID, collection_id: uuid_pkg.UUID, mode: str, session: Session) -> int:
        """检查是否有足够的单词进行复习（排除已在进行中考试的单词）"""

        # 1. 查找当前用户所有未完成的考试
        active_exams = session.exec(
            select(Exam.id).where(
                Exam.user_id == user_id,
                Exam.exam_status.in_(["generated", "grading"])
            )
        ).all()

        active_word_ids = []
        if active_exams:
             active_word_ids = session.exec(
                select(ExamSpellingSection.word_id).where(
                    ExamSpellingSection.exam_id.in_(active_exams)
                )
            ).all()

        # 2. 构建查询
        query = select(func.count()).select_from(UserWordItem).where(
            UserWordItem.user_id == user_id,
            UserWordItem.collection_id == collection_id
        )

        if active_word_ids:
            query = query.where(UserWordItem.word_id.notin_(active_word_ids))

        if mode == "complete":
            query = query.where(UserWordItem.status == 3)
        else:
            # immediate or random: status = 2
            query = query.where(UserWordItem.status == 2)

        return session.exec(query).one()

    @staticmethod
    async def process_exam_generation(
        exam_id: uuid_pkg.UUID,
        mode: str,
        target_count: int,
        session: Session
    ):
        """后台任务：执行考试生成逻辑"""
        try:
            exam = session.get(Exam, exam_id)
            if not exam:
                return

            user = session.get(User, exam.user_id)

            # 1. 根据模式筛选单词
            query = select(UserWordItem, WordBook).join(
                WordBook, UserWordItem.word_id == WordBook.id
            ).where(
                UserWordItem.collection_id == exam.collection_id,
                UserWordItem.user_id == exam.user_id
            )

            # --- 排除已在其他未完成考试（generated, grading）中使用的单词 ---
            # 1. 查找当前用户所有未完成的考试
            active_exams = session.exec(
                select(Exam.id).where(
                    Exam.user_id == exam.user_id,
                    Exam.exam_status.in_(["generated", "grading"]),
                    Exam.id != exam.id  # 排除自己
                )
            ).all()

            if active_exams:
                # 2. 查找这些考试已经包含的 word_id (从 ExamSpellingSection 表查)
                active_word_ids = session.exec(
                    select(ExamSpellingSection.word_id).where(
                        ExamSpellingSection.exam_id.in_(active_exams)
                    )
                ).all()

                if active_word_ids:
                    # 3. 在本次查询中排除这些 word_id
                    query = query.where(UserWordItem.word_id.notin_(active_word_ids))
            # -----------------------------------------------------------

            # 模式逻辑
            if mode == "immediate":
                # 即时复习：Status=2, 按最后复习时间倒序 (或者按 next_review_due 升序?)
                # 需求设计: "挑选20个最近更新（last_review_time）且状态为复习中（status为2）"
                # 最近更新意味着 last_review_time 越大越靠前
                query = query.where(UserWordItem.status == 2).order_by(desc(UserWordItem.last_review_time))
            elif mode == "random":
                # 随机复习：Status=2, 随机
                query = query.where(UserWordItem.status == 2)
            elif mode == "complete":
                # 完全复习：Status=3, 打乱 (根据需求 Line 8: "所有考试单词均来自状态为 3 的单词中" - 但 Line 31 说是完全复习)
                # 综合判断: 完全复习针对 Status 3 (Ready for Final), 成功后 -> 4
                query = query.where(UserWordItem.status == 3)
            else:
                # 默认 fallback
                query = query.where(UserWordItem.status == 2)

            all_items = session.exec(query).all()

            # 选择单词
            if mode == "random" or mode == "complete":
                selected_items = random.sample(all_items, min(target_count, len(all_items)))
            else:
                # immediate 已经排序过，取前N个
                selected_items = all_items[:target_count]

            if not selected_items:
                exam.exam_status = "failed"
                exam.generation_error = "没有符合条件的单词可供复习（可能单词已在其他未完成的考试中）"
                session.add(exam)
                session.commit()
                # 发送失败消息
                MessageService.create_message(session, user.id, "考试生成失败", "没有找到符合条件的单词，或者所有符合条件的单词都已在其他未完成的考试中。")
                return

            # 2. 生成拼写部分 (保存到数据库)
            exam_word_ids = [] # 记录本次考试涉及的所有 Word ID (UUID)
            words_text_list = [] # 单词文本列表，供LLM造句

            for item, word in selected_items:
                spelling_section = ExamSpellingSection(
                    exam_id=exam.id,
                    word_id=word.id,
                    item_id=item.id, # Save item_id
                    chinese_meaning=word.content.get("chinese", "未知含义"),
                    english_answer=word.word
                )
                session.add(spelling_section)

                exam_word_ids.append(word.id)
                words_text_list.append(word.word)

            # 3. 生成翻译部分 (调用LLM)
            # 随机选出几个词（不超过10个）用于造句
            sentence_words_candidates = random.sample(words_text_list, min(10, len(words_text_list)))

            llm_service = get_llm_service_for_user(user)
            # 生成 3-5 个句子
            generated_sentences = await llm_service.generate_exam_sentences(
                words=sentence_words_candidates,
                count=len(sentence_words_candidates),
                sentence_count=min(5, max(3, len(sentence_words_candidates) // 2))
            )

            for i, sent_data in enumerate(generated_sentences):
                # 找出句子涉及的单词ID
                involved_word_ids = []
                used_words = sent_data.get("words_used", [])
                for w_text in used_words:
                    # 简单匹配找到对应的 UUID (可能有重名单词，这里简单处理取当前选中的)
                    for item, word in selected_items:
                        if word.word.lower() == w_text.lower():
                            involved_word_ids.append(item.id)
                            break

                translation_section = ExamTranslationSection(
                    exam_id=exam.id,
                    sentence_id=f"sent_{exam.id}_{i}",
                    chinese_sentence=sent_data.get("chinese", ""),
                    words_involved=involved_word_ids
                )
                session.add(translation_section)

            # 4. 更新考试状态
            exam.exam_status = "generated"
            exam.spelling_words_count = len(selected_items)
            exam.translation_sentences_count = len(generated_sentences)
            session.add(exam)
            session.commit()

            # 5. 发送通知
            MessageService.create_message(
                session,
                user.id,
                "即时复习 - 考试生成完成",
                f"您的复习试卷已生成！包含 {len(selected_items)} 个单词和 {len(generated_sentences)} 个句子。请前往复习列表查看。"
            )

        except Exception as e:
            print(f"Error generating exam: {e}")
            if exam:
                exam.exam_status = "failed"
                exam.generation_error = str(e)
                session.add(exam)
                session.commit()
                MessageService.create_message(session, exam.user_id, "考试生成失败", f"系统错误: {str(e)}")

    @staticmethod
    def get_user_exams(
        user_id: uuid_pkg.UUID,
        page: int,
        size: int,
        session: Session,
        mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取用户考试列表"""
        offset = (page - 1) * size

        # Base query
        query = select(Exam).where(Exam.user_id == user_id)
        if mode:
            query = query.where(Exam.mode == mode)

        statement = query.order_by(desc(Exam.created_at)).offset(offset).limit(size)
        exams = session.exec(statement).all()

        # Count total
        count_query = select(func.count()).select_from(Exam).where(Exam.user_id == user_id)
        if mode:
            count_query = count_query.where(Exam.mode == mode)

        total = session.exec(count_query).one()

        exam_infos = []
        for ex in exams:
            # 获取 collection name
            coll = session.get(WordCollection, ex.collection_id)
            coll_name = coll.name if coll else "未知单词本"

            exam_infos.append({
                "exam_id": ex.id,
                "user_id": ex.user_id,
                "collection_name": coll_name,
                "total_words": ex.total_words,
                "spelling_words_count": ex.spelling_words_count,
                "translation_sentences_count": ex.translation_sentences_count,
                "exam_status": ex.exam_status,
                "created_at": ex.created_at,
                "completed_at": ex.completed_at
            })

        return {
            "exams": exam_infos,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "total_pages": (total + size - 1) // size
            }
        }

    @staticmethod
    def check_review_availability(user_id: uuid_pkg.UUID, collection_id: uuid_pkg.UUID, mode: str, session: Session) -> int:
        """检查是否有足够的单词进行复习（排除已在进行中考试的单词）"""

        # 1. 查找当前用户所有未完成的考试
        active_exams = session.exec(
            select(Exam.id).where(
                Exam.user_id == user_id,
                Exam.exam_status.in_(["generated", "grading"])
            )
        ).all()

        active_word_ids = []
        if active_exams:
             active_word_ids = session.exec(
                select(ExamSpellingSection.word_id).where(
                    ExamSpellingSection.exam_id.in_(active_exams)
                )
            ).all()

        # 2. 构建查询
        query = select(func.count()).select_from(UserWordItem).where(
            UserWordItem.user_id == user_id,
            UserWordItem.collection_id == collection_id
        )

        if active_word_ids:
            query = query.where(UserWordItem.word_id.notin_(active_word_ids))

        if mode == "complete":
            query = query.where(UserWordItem.status == 3)
        else:
            # immediate or random: status = 2
            query = query.where(UserWordItem.status == 2)

        return session.exec(query).one()
    @staticmethod
    def get_exam_detail(exam_id: uuid_pkg.UUID, session: Session) -> Optional[Dict[str, Any]]:
        """获取考试详情（包含题目预览）"""
        exam = session.get(Exam, exam_id)
        if not exam:
            return None

        coll = session.get(WordCollection, exam.collection_id)

        # 获取部分题目作为预览/加载内容
        spelling_sections = session.exec(select(ExamSpellingSection).where(ExamSpellingSection.exam_id == exam_id)).all()
        translation_sections = session.exec(select(ExamTranslationSection).where(ExamTranslationSection.exam_id == exam_id)).all()

        # 格式化拼写部分
        spelling_list = []
        for s in spelling_sections:
            spelling_list.append({
                "word_id": s.word_id,
                "item_id": s.item_id, # Return item_id to frontend
                "chinese": s.chinese_meaning,
                "english_answer": s.english_answer # 前端需要答案进行本地判断?
                # 需求设计: "默写与翻译两个部分，默写部分的单词的英文答案使用匹配的方法（由前端完成）" -> 是的，需要返回答案
            })

        # 格式化翻译部分
        translation_list = []
        for t in translation_sections:
            translation_list.append({
                "sentence_id": t.sentence_id,
                "chinese": t.chinese_sentence,
                "words_involved": t.words_involved # Returns UUID list
            })

        return {
            "exam_id": exam.id,
            "user_id": exam.user_id,
            "collection_id": exam.collection_id,
            "collection_name": coll.name if coll else "未知",
            "exam_status": exam.exam_status,
            "total_words": exam.total_words,
            "spelling_words_count": exam.spelling_words_count,
            "translation_sentences_count": exam.translation_sentences_count,
            "estimated_duration_minutes": exam.total_words, # 1 min per word rule
            "created_at": exam.created_at,
            "completed_at": exam.completed_at,
            "spelling_section": spelling_list,
            "translation_section": translation_list
        }

    @staticmethod
    def check_review_availability(user_id: uuid_pkg.UUID, collection_id: uuid_pkg.UUID, mode: str, session: Session) -> int:
        """检查是否有足够的单词进行复习（排除已在进行中考试的单词）"""

        # 1. 查找当前用户所有未完成的考试
        active_exams = session.exec(
            select(Exam.id).where(
                Exam.user_id == user_id,
                Exam.exam_status.in_(["generated", "grading"])
            )
        ).all()

        active_word_ids = []
        if active_exams:
             active_word_ids = session.exec(
                select(ExamSpellingSection.word_id).where(
                    ExamSpellingSection.exam_id.in_(active_exams)
                )
            ).all()

        # 2. 构建查询
        query = select(func.count()).select_from(UserWordItem).where(
            UserWordItem.user_id == user_id,
            UserWordItem.collection_id == collection_id
        )

        if active_word_ids:
            query = query.where(UserWordItem.word_id.notin_(active_word_ids))

        if mode == "complete":
            query = query.where(UserWordItem.status == 3)
        else:
            # immediate or random: status = 2
            query = query.where(UserWordItem.status == 2)

        return session.exec(query).one()
    @staticmethod
    def mark_exam_as_grading(exam_id: uuid_pkg.UUID, session: Session):
        """将考试状态标记为阅卷中"""
        exam = session.get(Exam, exam_id)
        if exam:
            exam.exam_status = "grading"
            session.add(exam)
            session.commit()

    @staticmethod
    async def submit_exam(
        exam_id: uuid_pkg.UUID,
        user_id: uuid_pkg.UUID,
        wrong_word_ids: List[uuid_pkg.UUID],
        sentences_submission: List[Dict], # [{sentence_id, chinese, english, words_involved}]
        session: Session
    ) -> Dict[str, Any]:
        """提交考试，评分并更新状态"""
        exam = session.get(Exam, exam_id)
        if not exam:
            raise ValueError("Exam not found")

        user = session.get(User, user_id)

        # 1. 处理默写错误 (Wrong Words -> Status 0)
        failed_word_ids_set = set(wrong_word_ids)

        # 2. 处理翻译 (LLM Judge)
        llm_service = get_llm_service_for_user(user)
        translation_results = []

        for sent_sub in sentences_submission:
            sentence_id = sent_sub.get("sentence_id")
            chinese = sent_sub.get("chinese")
            english_user = sent_sub.get("english")
            words_involved = sent_sub.get("words_involved", []) # This might be UUIDs or strings depending on frontend

            # 获取关联单词的英文原词
            required_words_text = []
            for w_id in words_involved:
                try:
                    stmt = select(WordBook).join(UserWordItem, UserWordItem.word_id == WordBook.id).where(UserWordItem.id == uuid_pkg.UUID(str(w_id)))
                    word_obj = session.exec(stmt).first()
                    if word_obj:
                        required_words_text.append(word_obj.word)
                except Exception:
                    pass

            # 使用 LLM 评判
            grading_result = await llm_service.grade_translation(
                source_text=chinese,
                user_translation=english_user,
                required_words=required_words_text
            )
            is_correct = grading_result.get("correct", False)

            translation_results.append({
                "sentence_id": sentence_id,
                "chinese": chinese,
                "your_answer": english_user,
                "is_correct": is_correct,
                "feedback": grading_result.get("feedback", "")
            })

            if not is_correct:
                # 翻译错误，涉及单词 status -> 0
                for w_id in words_involved:
                    # w_id might be string format UUID
                    try:
                        w_uuid = uuid_pkg.UUID(str(w_id))
                        failed_word_ids_set.add(w_uuid)
                    except:
                        pass

        # 3. 更新数据库状态
        # 获取考试所有涉及单词
        all_spelling = session.exec(select(ExamSpellingSection).where(ExamSpellingSection.exam_id == exam_id)).all()
        # 使用 item_id 进行集合运算
        all_exam_item_ids = {s.item_id for s in all_spelling}

        # 正确单词 = 所有单词 - 失败单词
        passed_item_ids = all_exam_item_ids - failed_word_ids_set

        # 更新失败单词 -> 0
        for item_id in failed_word_ids_set:
            uw_item = session.get(UserWordItem, item_id)
            # 确保条目存在且属于当前用户（安全检查）
            if uw_item and uw_item.user_id == user_id:
                uw_item.status = 0
                uw_item.fail_count += 1
                session.add(uw_item)

        # 更新通过单词 -> +1
        for item_id in passed_item_ids:
            uw_item = session.get(UserWordItem, item_id)
            if uw_item and uw_item.user_id == user_id:
                # 根据考试模式更新状态
                if exam.mode in ['immediate', 'random']:
                    # 即时/随机复习：Status 2 -> 3 (Max 3)
                    if uw_item.status == 2:
                        uw_item.status = 3
                elif exam.mode == 'complete':
                    # 完全复习：Status 3 -> 4
                    if uw_item.status == 3:
                        uw_item.status = 4

                uw_item.review_count += 1
                uw_item.last_review_time = datetime.now()
                session.add(uw_item)

        # 4. 更新考试记录
        exam.exam_status = "completed"
        exam.completed_at = datetime.now()
        session.add(exam)

        session.commit()

        # 5. 发送站内信结果
        msg_content = (
            f"考试已完成！\n"
            f"总单词数: {len(all_exam_item_ids)}\n"
            f"拼写正确: {len(passed_item_ids)}\n"
            f"拼写错误: {len(failed_word_ids_set)}\n\n"
            f"翻译结果:\n"
        )
        for res in translation_results:
            msg_content += f"- {res['chinese']}\n  您的翻译: {res['your_answer']}\n  判定: {'✅ 正确' if res['is_correct'] else '❌ 错误'}\n"

        MessageService.create_message(session, user_id, "考试结果通知", msg_content)

        return {"success": True, "message": "考试已提交，结果已发送至站内信"}

    @staticmethod
    def delete_exam(exam_id: uuid_pkg.UUID, user_id: uuid_pkg.UUID, session: Session) -> bool:
        """删除考试及其相关数据"""
        # 1. 获取考试
        exam = session.get(Exam, exam_id)
        if not exam:
            return False # 或者抛出异常

        # 验证归属
        if exam.user_id != user_id:
            raise ValueError("无权删除此考试")

        # 检查考试状态：仅允许删除已完成的考试
        if exam.exam_status != "completed":
            raise ValueError("仅能删除已完成的考试记录")

        # 2. 删除关联的题目数据 (如果数据库没设置级联删除，这里手动删除)
        # 实际上 SQLModel 的 delete() 方法可能不直接支持 exec().delete()，通常是用 session.delete(obj)
        # 为了稳妥，先查再删，或者使用 delete 语句
        # SQLModel 0.0.16+ 支持 session.exec(delete(...))
        from sqlmodel import delete
        session.exec(delete(ExamSpellingSection).where(ExamSpellingSection.exam_id == exam_id))
        session.exec(delete(ExamTranslationSection).where(ExamTranslationSection.exam_id == exam_id))

        # 3. 删除考试记录
        session.delete(exam)
        session.commit()
        return True
