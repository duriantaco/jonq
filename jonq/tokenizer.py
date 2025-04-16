import re
from enum import Enum, auto

class TokenType(Enum):
    KEYWORD = auto()     # select, if, group, by, having, etc.
    IDENTIFIER = auto()  # field names, table names
    FUNCTION = auto()    # sum, avg, count, etc.
    OPERATOR = auto()    # +, -, *, /, =, >, <, >=, <=, !=
    STRING = auto()      # 'text', "text"
    NUMBER = auto()      # 123, 45.67
    PUNCTUATION = auto() # (, ), ,
    WILDCARD = auto()    # *

class Token:
    def __init__(self, type, value, position=None):
        self.type = type
        self.value = value
        self.position = position

    def __repr__(self):
        return f"Token({self.type}, '{self.value}')"

def tokenize_with_lexer(query):
    token_specs = [
        ('WHITESPACE', r'\s+'),
        ('KEYWORD', r'\b(?i:select|if|sort|group|by|having|as|and|or|asc|desc|from)\b'),
        ('FUNCTION_CALL', r'\w+\s*\(\s*\*\s*\)'),
        ('FUNCTION_PARAM', r'\w+\s*\(\s*[\w\.\[\]]+\s*\)'),
        ('OPERATOR', r'<=|>=|!=|=|<|>|\+|\*|\/'),
        ('ARITHMETIC_MINUS', r'\s-\s'),
        ('STRING', r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''),
        ('NUMBER', r'\d+(?:\.\d+)?'),
        ('IDENTIFIER', r'[\w\.\[\]\-]+'),
        ('PUNCTUATION', r'[,\(\)]'),
        ('INVALID', r'.'),
    ]

    token_regex = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in token_specs)

    pos = 0
    tokens = []

    for match in re.finditer(token_regex, query):
        token_type = match.lastgroup
        if token_type == 'WHITESPACE':
            continue
        elif token_type == 'INVALID':
            value = match.group()
            position = match.start()
            raise ValueError(f"Invalid character '{value}' at position {position}")

        value = match.group()
        position = match.start()

        if token_type == 'FUNCTION_CALL':
            func_name = re.match(r'^(\w+)\s*\(', value).group(1)
            tokens.append(Token(TokenType.FUNCTION, func_name, position))
            tokens.append(Token(TokenType.PUNCTUATION, '(', position + len(func_name)))
            tokens.append(Token(TokenType.WILDCARD, '*', position + len(func_name) + 1))
            tokens.append(Token(TokenType.PUNCTUATION, ')', position + len(value) - 1))

        elif token_type == 'FUNCTION_PARAM':
            func_name = re.match(r'^(\w+)\s*\(', value).group(1)
            param = re.search(r'\(\s*([\w\.\[\]]+)\s*\)', value).group(1)
            tokens.append(Token(TokenType.FUNCTION, func_name, position))
            tokens.append(Token(TokenType.PUNCTUATION, '(', position + len(func_name)))
            tokens.append(Token(TokenType.IDENTIFIER, param, position + len(func_name) + 1))
            tokens.append(Token(TokenType.PUNCTUATION, ')', position + len(value) - 1))

        elif token_type == 'KEYWORD':
            tokens.append(Token(TokenType.KEYWORD, value.lower(), position))

        elif token_type == 'OPERATOR':
            tokens.append(Token(TokenType.OPERATOR, value, position))
            
        elif token_type == 'ARITHMETIC_MINUS':
            tokens.append(Token(TokenType.OPERATOR, '-', position))

        elif token_type == 'STRING':
            tokens.append(Token(TokenType.STRING, value, position))

        elif token_type == 'NUMBER':
            tokens.append(Token(TokenType.NUMBER, value, position))

        elif token_type == 'IDENTIFIER':
            tokens.append(Token(TokenType.IDENTIFIER, value, position))

        elif token_type == 'PUNCTUATION':
            tokens.append(Token(TokenType.PUNCTUATION, value, position))

        pos = match.end()

    if pos < len(query) and not query[pos:].isspace():
        raise ValueError(f"Unexpected character '{query[pos]}' at position {pos}")

    simple_tokens = [token.value for token in tokens]
    return simple_tokens
def tokenize(query):
    return tokenize_with_lexer(query)