"""Bounded decimal arithmetic, without Python evaluation or engineering decisions."""

import re
from decimal import Decimal, DecimalException, localcontext

from pydantic import BaseModel, ConfigDict, Field

from agents.tools.base import ToolResult


class CalculateArgs(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expression: str = Field(min_length=1, max_length=200)


def calculate(args: CalculateArgs) -> ToolResult:
    try:
        if re.search(r'[\d.]\s+[\d.]', args.expression):
            raise ValueError('Separated number')
        text = re.sub(r'\s+', '', args.expression)
        tokens = re.findall(r'(?:\d+(?:\.\d*)?|\.\d+)|[()+*/-]', text)
        if ''.join(tokens) != text or not tokens or len(tokens) > 80:
            raise ValueError('Unsupported expression')
        index = 0

        def expression(depth=0):
            nonlocal index
            value = term(depth)
            while index < len(tokens) and tokens[index] in ('+', '-'):
                op = tokens[index]
                index += 1
                other = term(depth)
                value = value + other if op == '+' else value - other
            return value

        def term(depth):
            nonlocal index
            value = factor(depth)
            while index < len(tokens) and tokens[index] in ('*', '/'):
                op = tokens[index]
                index += 1
                other = factor(depth)
                value = value * other if op == '*' else value / other
                if not value.is_finite() or abs(value) > Decimal('1e30'):
                    raise ValueError('Out of bounds')
            return value

        def factor(depth):
            nonlocal index
            if depth > 12 or index >= len(tokens):
                raise ValueError('Expression depth or missing operand')
            token = tokens[index]
            index += 1
            if token in ('+', '-'):
                return factor(depth + 1) * (-1 if token == '-' else 1)
            if token == '(':
                value = expression(depth + 1)
                if index >= len(tokens) or tokens[index] != ')':
                    raise ValueError('Unbalanced expression')
                index += 1
                return value
            if token in (')', '*', '/') or len(token) > 30:
                raise ValueError('Invalid number')
            return Decimal(token)

        with localcontext() as context:
            context.prec = 28
            value = expression()
            if index != len(tokens) or not value.is_finite() or abs(value) > Decimal('1e30'):
                raise ValueError('Out of bounds')
            result = format(value, '.12f').rstrip('0').rstrip('.')
            if result in ('', '-0'):
                result = '0'
        return ToolResult(tool_name='calculate', ok=True, summary='已完成基础算术计算；单位与工程适用性仍需核对。',
                          data={'expression': args.expression, 'result': result, 'decimal_places': 12,
                                'limitation': '最多保留12位小数；不校核单位、规范阈值、承载力或安全结论。'})
    except (ValueError, DecimalException):
        return ToolResult(tool_name='calculate', ok=False, summary='仅支持有限长度的十进制四则运算与括号；请检查除零、表达式或数值范围。',
                          error_code='invalid_calculation')
