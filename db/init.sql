-- データベースの作成
CREATE DATABASE IF NOT EXISTS task CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- データベースを使用
USE task;

-- Lectureテーブルの作成
CREATE TABLE IF NOT EXISTS Lecture (
    id INT AUTO_INCREMENT PRIMARY KEY, -- 授業エントリのID
    title VARCHAR(255) NOT NULL, -- 授業のタイトル名 e.g., 課題1, 課題2, ...
    start_date TIMESTAMP NOT NULL, -- 課題ページの公開日
    end_date TIMESTAMP NOT NULL -- 課題ページの公開終了日
);

-- Problemテーブルの作成
CREATE TABLE IF NOT EXISTS Problem (
    lecture_id INT, -- Lecture.idからの外部キー
    assignment_id INT, -- 何番目の課題か, e.g., 1, 2, ...
    for_evaluation BOOLEAN, -- 課題採点用かどうか, True/False
    title VARCHAR(255) NOT NULL, -- 課題名 e.g., 基本課題1
    description_path VARCHAR(255) NOT NULL, -- 課題の説明文のファイルパス
    timeMS INT NOT NULL, -- ジャッジの制限時間[ms] e.g., 1000
    memoryMB INT NOT NULL, -- ジャッジの制限メモリ[MB] e.g., 1024
    build_script_path VARCHAR(255) NOT NULL, -- ビルドする際に用いるスクリプトファイルのパス
    executable VARCHAR(255) NOT NULL, -- 最終的に得られる実行バイナリ名 e.g., main
    PRIMARY KEY (lecture_id, assignment_id, for_evaluation),
    FOREIGN KEY (lecture_id) REFERENCES Lecture(id)
);

-- SourceFilesテーブルの作成
CREATE TABLE IF NOT EXISTS SourceFiles (
    id INT AUTO_INCREMENT PRIMARY KEY, -- ソースコードのID(auto increment)
    lecture_id INT, -- 何回目の授業で出される課題か, e.g., 1, 2, ...
    assignment_id INT, -- 何番目の課題か, e.g., 1, 2, ...
    for_evaluation BOOLEAN, -- 課題採点用かどうか, True/False
    from_client BOOLEAN NOT NULL, -- 提出者からのソースコードか、用意されたものか, True/False
    path VARCHAR(255) NOT NULL, -- ソースコードのパス(Makefileも全部含める)
    FOREIGN KEY (lecture_id, assignment_id, for_evaluation) REFERENCES Problem(lecture_id, assignment_id, for_evaluation)
);

-- TestCasesテーブルの作成
CREATE TABLE IF NOT EXISTS TestCases (
    id INT AUTO_INCREMENT PRIMARY KEY, -- テストケースのID(auto increment)
    lecture_id INT, -- 何回目の授業で出される課題か, e.g., 1, 2, ...
    assignment_id INT, -- 何番目の課題か, e.g., 1, 2, ...
    for_evaluation BOOLEAN, -- 課題採点用かどうか, True/False
    description TEXT, -- どの部分点に相当するかの説明
    score INT, -- テストケースの配点, フォーマットチェック用だったらゼロ
    script_path VARCHAR(255), -- ./<実行バイナリ> の形式に合わない場合のスクリプトファイルのパス
    stdin_path VARCHAR(255) NOT NULL, -- 標準入力のパス, path/to/stdin.txt
    stdout_path VARCHAR(255) NOT NULL, -- 想定される標準出力のパス, path/to/stdout.txt
    stderr_path VARCHAR(255) NOT NULL, -- 想定される標準エラー出力のパス, path/to/stderr.txt
    FOREIGN KEY (lecture_id, assignment_id, for_evaluation) REFERENCES Problem(lecture_id, assignment_id, for_evaluation)
);

-- AdminUserテーブルの作成
CREATE TABLE IF NOT EXISTS AdminUser (
    id VARCHAR(255) PRIMARY KEY, -- ユーザID e.g., zakki
    name VARCHAR(255) NOT NULL -- ユーザ名 e.g., 山崎
);

-- Studentテーブルの作成
CREATE TABLE IF NOT EXISTS Student (
    id VARCHAR(255) PRIMARY KEY, -- 学籍番号 e.g., s2200342
    name VARCHAR(255) NOT NULL -- ユーザ名 e.g., 岡本
);

-- BatchSubmissionテーブルの作成
CREATE TABLE IF NOT EXISTS BatchSubmission (
    id INT AUTO_INCREMENT PRIMARY KEY, -- バッチ採点のID(auto increment)
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- バッチ採点のリクエスト時刻
    user_id VARCHAR(255), -- リクエストした管理者のID
    FOREIGN KEY (user_id) REFERENCES AdminUser(id)
);

-- Submissionテーブルの作成
CREATE TABLE IF NOT EXISTS Submission (
    id INT AUTO_INCREMENT PRIMARY KEY, -- 提出されたジャッジリクエストのID(auto increment)
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- リクエストされた時刻
    batch_id INT, -- ジャッジリクエストが属しているバッチリクエストのID, 学生のフォーマットチェック提出ならNULL
    student_id VARCHAR(255), -- 採点対象の学生の学籍番号
    lecture_id INT, -- 何回目の授業で出される課題か, e.g., 1, 2, ...
    assignment_id INT, -- 何番目の課題か, e.g., 1, 2, ...
    for_evaluation BOOLEAN, -- 課題採点用かどうか, True/False
    status ENUM('queued', 'running', 'done', 'failed') DEFAULT 'queued', -- リクエストの処理状況, queued/running/done/failed
    FOREIGN KEY (batch_id) REFERENCES BatchSubmission(id),
    FOREIGN KEY (student_id) REFERENCES Student(id),
    FOREIGN KEY (lecture_id, assignment_id, for_evaluation) REFERENCES Problem(lecture_id, assignment_id, for_evaluation)
);

-- UploadedFilesテーブルの作成
CREATE TABLE IF NOT EXISTS UploadedFiles (
    id INT AUTO_INCREMENT PRIMARY KEY, -- アップロードされたファイルのID(auto increment)
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- アップロードされた時刻
    submission_id INT, -- そのファイルが必要なジャッジリクエストのID
    path VARCHAR(255) NOT NULL, -- アップロードされたファイルのパス
    FOREIGN KEY (submission_id) REFERENCES Submission(id)
);

-- JudgeResultテーブルの作成
CREATE TABLE IF NOT EXISTS JudgeResult (
    id INT AUTO_INCREMENT PRIMARY KEY, -- ジャッジ結果のID(auto increment)
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- ジャッジ結果が出た時刻
    submission_id INT, -- ジャッジ結果に紐づいているジャッジリクエストのID
    testcase_id INT, -- ジャッジ結果に紐づいているテストケースのID
    timeMS INT NOT NULL, -- 実行時間[ms]
    memoryKB INT NOT NULL, -- 消費メモリ[KB]
    result ENUM('AC', 'WA', 'TLE', 'MLE', 'CE', 'RE', 'OLE', 'IE') NOT NULL, -- 実行結果のステータス、 AC/WA/TLE/MLE/CE/RE/OLE/IE, 参考: https://atcoder.jp/contests/abc367/glossary
    FOREIGN KEY (submission_id) REFERENCES Submission(id),
    FOREIGN KEY (testcase_id) REFERENCES TestCases(id)
);
