# エラーメッセージの型
class Error:
    message: str  # エラーメッセージ

    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"Error(message=\"{self.message}\")"
