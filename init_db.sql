-- WordMaster Database Initialization Script
-- Database: wordmaster_db
-- Username: wordmaster
--
-- Features:
-- 1. Global shared wordbook table
-- 2. User-specific word collections
-- 3. Notification system (messages)
-- 4. Exam system with spelling and translation sections
-- 5. Cascade delete protection and automatic word counting

-- 1. Create users table (with LLM configuration)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nickname VARCHAR(50),
    avatar_url VARCHAR(255),

    -- LLM Configuration
    use_default_llm BOOLEAN DEFAULT TRUE NOT NULL,
    llm_api_key VARCHAR(500),
    llm_base_url VARCHAR(255),
    llm_model VARCHAR(100),

    last_login_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_email ON users(email);

-- Create trigger function for updating updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 2. Create user_sessions table
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(500) NOT NULL,
    refresh_token VARCHAR(500),
    device_info VARCHAR(255),
    ip_address VARCHAR(50),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_session_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_session_token ON user_sessions(token);
CREATE INDEX IF NOT EXISTS idx_session_expires_at ON user_sessions(expires_at);

-- 3. Create wordbook table (Global shared word library)
CREATE TABLE IF NOT EXISTS wordbook (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    word VARCHAR(100) NOT NULL UNIQUE,
    content JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_word ON wordbook(word);
CREATE INDEX IF NOT EXISTS idx_wordbook_content ON wordbook USING GIN (content);

-- 4. Create word_collections table (Word collection categories)
CREATE TABLE IF NOT EXISTS word_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    color VARCHAR(20),
    icon VARCHAR(50),
    word_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_collections_user_id ON word_collections(user_id);
CREATE INDEX IF NOT EXISTS idx_collections_created_at ON word_collections(created_at DESC);

CREATE TRIGGER update_word_collections_updated_at
    BEFORE UPDATE ON word_collections
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 5. Create user_word_items table (User word learning items)
CREATE TABLE IF NOT EXISTS user_word_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES word_collections(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    word_id UUID NOT NULL REFERENCES wordbook(id) ON DELETE RESTRICT,
    status INTEGER DEFAULT 0 NOT NULL CHECK (status IN (0, 1, 2, 3, 4)),
    review_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    match_count INTEGER DEFAULT 0,
    study_count INTEGER DEFAULT 0,
    last_review_time TIMESTAMP,
    next_review_due TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (collection_id, word_id)
);

CREATE INDEX IF NOT EXISTS idx_items_collection_id ON user_word_items(collection_id);
CREATE INDEX IF NOT EXISTS idx_items_user_id ON user_word_items(user_id);
CREATE INDEX IF NOT EXISTS idx_items_word_id ON user_word_items(word_id);
CREATE INDEX IF NOT EXISTS idx_items_status ON user_word_items(status);
CREATE INDEX IF NOT EXISTS idx_items_next_review ON user_word_items(next_review_due) WHERE next_review_due IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_items_collection_status ON user_word_items(collection_id, status);
CREATE INDEX IF NOT EXISTS idx_items_collection_review ON user_word_items(collection_id, next_review_due) WHERE status < 4;

CREATE TRIGGER update_user_word_items_updated_at
    BEFORE UPDATE ON user_word_items
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 6. Trigger to update word_count in word_collections
CREATE OR REPLACE FUNCTION update_collection_word_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE word_collections SET word_count = word_count + 1 WHERE id = NEW.collection_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE word_collections SET word_count = word_count - 1 WHERE id = OLD.collection_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_collection_count_on_insert
    AFTER INSERT ON user_word_items
    FOR EACH ROW EXECUTE FUNCTION update_collection_word_count();

CREATE TRIGGER update_collection_count_on_delete
    AFTER DELETE ON user_word_items
    FOR EACH ROW EXECUTE FUNCTION update_collection_word_count();

-- 7. Create messages table (Notification system)
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);

-- 8. Create exams table
CREATE TABLE IF NOT EXISTS exams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    collection_id UUID NOT NULL REFERENCES word_collections(id) ON DELETE CASCADE,
    exam_status VARCHAR(20) DEFAULT 'pending' CHECK (exam_status IN ('pending', 'generated', 'grading', 'completed', 'failed')),
    mode VARCHAR(20) DEFAULT 'immediate',
    total_words INTEGER NOT NULL,
    spelling_words_count INTEGER NOT NULL,
    translation_sentences_count INTEGER NOT NULL,
    generation_error TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_exams_user_id ON exams(user_id);
CREATE INDEX IF NOT EXISTS idx_exams_collection_id ON exams(collection_id);
CREATE INDEX IF NOT EXISTS idx_exams_status ON exams(exam_status);

-- 9. Create exam_spelling_sections table
CREATE TABLE IF NOT EXISTS exam_spelling_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    word_id UUID NOT NULL REFERENCES wordbook(id) ON DELETE CASCADE,
    item_id UUID REFERENCES user_word_items(id) ON DELETE CASCADE,
    chinese_meaning TEXT NOT NULL,
    english_answer TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_exam_spelling_exam_id ON exam_spelling_sections(exam_id);
CREATE INDEX IF NOT EXISTS idx_exam_spelling_word_id ON exam_spelling_sections(word_id);
CREATE INDEX IF NOT EXISTS idx_exam_spelling_item_id ON exam_spelling_sections(item_id);

-- 10. Create exam_translation_sections table
CREATE TABLE IF NOT EXISTS exam_translation_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id UUID NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    sentence_id VARCHAR(50) NOT NULL,
    chinese_sentence TEXT NOT NULL,
    words_involved UUID[], -- Array of UUIDs from wordbook/items
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_exam_translation_exam_id ON exam_translation_sections(exam_id);

-- 11. Cleanup and Success Message
DROP TABLE IF EXISTS user_progress CASCADE;

DO $$
BEGIN
    RAISE NOTICE 'WordMaster Database Initialization Completed!';
    RAISE NOTICE 'Tables created: users, sessions, wordbook, collections, items, messages, exams, exam_sections';
END $$;
