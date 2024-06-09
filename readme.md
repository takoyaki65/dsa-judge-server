# dsa-judge-server
## 背景・目的

## 検討した別の方法

## 要件
* クライアントは、実行してほしいタスク(ソースコード、制限時間、制限メモリ、etc)をまとめた`task.zip`をdsa-judge-serverに送信する。task.zipの展開後のディレクトリ構成は任意でよいが、必ずトップディレクトリに`task.yaml`が存在すること。`task.zip`を受け取った後、クライアントに対してジョブID(UUID)を返し、`task.zip`を展開してタスクを実行する。
* クライアントはタスクのUUIDをサーバに問い合わせることで、タスクの実行状況を`status.json`で取得できる。
![alt text](image.png)

* task.yamlには、実行すべきジョブの情報が記録されている。ジョブの情報とは、以下のようなものである。なお、実行するプログラムは一つで、引数は固定であるとする。
  * ソースコードの相対パス
  * ソースコードの言語
  * ビルドコマンド
  * プログラム名
  * 引数リスト
  * グローバルな制限時間 (ms)
  * グローバルな制限メモリ (MB)
  * テストケースのエントリ(複数あり)
    * 標準入力に流す入力ファイルの相対パス (e.g., `test00.in`)
    * 想定される標準出力のファイルの相対パス (e.g., `test00.out`)
    * 想定される標準エラー出力のファイルの相対パス (e.g., `test00.err`)
    * 出力のチェッカー
      * `standard`: 標準出力と想定される出力が完全に一致すること
      * `easy`: 標準出力と想定される出力が完全に一致すること。ただし、空白・改行文字は無視する
      * ``[`float`, precision]``: 標準出力と想定される出力が完全に一致すること。ただし、浮動小数点数の比較を行い、その誤差が`precision`以下であること
      * ``[`line`, `checker`]``: 各行について、`checker`でチェックを行う
    * 想定される終了コード (e.g., 0)
```yaml
source: src/main.c
language: c
build: gcc -o main src/main.c
program: main
args: []
timeMs: 1000
memoryMB: 256
testcases:
  - input: test00.in
    output: test00.out
    error: test00.err
    checker: standard
    exitCode: 0
  - input: test01.in
    output: test01.out
    error: test01.err
    checker: easy
    exitCode: 0
```

* サーバは、タスクの実行状況を`status.json`で返す。`status.json`は以下のような形式である。
```json
{
  "status": "running",
  "progress": 0.5,
  "result": {
    "test00": {
      "status": "AC" // AC, WA, RE, TLE, MLE
      "timeMs": 100,
      "memoryMB": 256
      "stdout": "Hello, World!\n",
      "stderr": ""
    },
    "test01": {
      "status": "running"
    }
  }
}
```

## 設計
FastAPIを用いて、REST APIを提供する。APIは以下のエンドポイントを提供する。
* `POST /task`: タスクを登録する。タスクのUUIDを返す。
* `GET /task/{task_id}`: タスクの状態を取得する。
* `GET /task/{task_id}/result`: タスクの結果を取得する。

judgeサーバーはDockerコンテナで動かす。実際にユーザが提出するプログラムは、judgeサーバーが
生成したDockerコンテナ内でビルド・実行される。Docker生成は、ホストのDockerデーモンを利用する。

## セキュリティ上の懸念
JudgeサーバーのDockerソケットをホストマシンのDocker Engineに接続することで、
コンテナ内からホストのDocker Engineを操作できる。これにより、このJudgeサーバーに
侵入した悪意のあるユーザが、ホストマシン上の全てのコンテナを操作してしまう可能性がある。
これにより、ホストのroot権限を奪われる可能性がある？。

https://speakerdeck.com/narupi/dockerkontenakarahosutofalserootwoqu-ruhua?slide=10

対策としては、このJudgeサーバーのendpointにアクセス制限をかけることが考えられる。

