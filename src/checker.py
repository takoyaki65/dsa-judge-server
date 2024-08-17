class StandardChecker:
    @staticmethod
    def check(ls: str, rs: str) -> bool:
        # 末尾の改行を削除
        ls = ls.rstrip('\n')
        rs = rs.rstrip('\n')

        # 行に分割
        ls_lines = ls.split('\n')
        rs_lines = rs.split('\n')

        # 行数が異なる場合はFalse
        if len(ls_lines) != len(rs_lines):
            return False

        # 各行を比較
        for ls_line, rs_line in zip(ls_lines, rs_lines):
            if ls_line.split() != rs_line.split():
                return False

        return True