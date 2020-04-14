
class IP:
    # Implements a simple IPv4 address

    def __init__(self, s=None):
        self.ip = tuple()
        self.ip_str = ""

        if s is not None:
            self.ip_str = s
            self._from_str(self.ip_str)

    def __eq__(self, other):
        eq = 0
        for i in range(0, 4):
            if self.ip == other.ip:
                eq += 1

        if eq == 4:
            return True
        else:
            return False

    def __str__(self):
        return self.ip_str

    def _from_str(self, string):

        dot_count = 0
        for c in string:
            if c.isdigit():
                pass
            else:
                if c == '.' and dot_count < 3:
                    dot_count += 1
                    pass
                else:
                    raise ValueError("Invalid IP.")

        str_values = string.split(".")
        int_values = tuple([int(x) for x in str_values])

        for val in int_values:
            if val > 256:
                raise ValueError("Invalid IP.")

        self.ip = int_values
