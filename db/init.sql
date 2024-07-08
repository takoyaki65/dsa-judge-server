-- データベースの作成
CREATE DATABASE IF NOT EXISTS task CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- データベースを使用
USE task;

-- テーブルの作成
CREATE TABLE IF NOT EXISTS task (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    path_to_dir VARCHAR(255) NOT NULL,
    status ENUM('pending', 'processing', 'done') DEFAULT 'pending'
);
