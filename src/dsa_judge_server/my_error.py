# エラーメッセージの型
class Error:
    message: str  # エラーメッセージ

    def __init__(self, message: str):
        self.message = message
