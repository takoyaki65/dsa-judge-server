# 前提
パッケージマネージャ`rye`をインストールしていること。

# パッケージの追加方法
`rye`を使ってパッケージを追加するには、以下のコマンドを実行します。

```bash
rye add <package-name>
```

追加したパッケージをrequirements.lockに更新するには、以下のコマンドを実行します。

```bash
rye sync
```