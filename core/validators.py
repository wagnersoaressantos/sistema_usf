import re
from django.core.exceptions import ValidationError

def validar_cpf(value):
    # 1. Se estiver vazio (só Cartão SUS), deixa passar
    if not value:
        return

    cpf = ''.join(re.findall(r'\d', str(value)))

    if len(cpf) != 11 or cpf in (c * 11 for c in "0123456789"):
        raise ValidationError('CPF inválido. Verifique os números digitados.')

    # Cálculo do 1º dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digito_1 = (soma * 10 % 11) % 10

    # Cálculo do 2º dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digito_2 = (soma * 10 % 11) % 10

    if str(digito_1) != cpf[9] or str(digito_2) != cpf[10]:
        raise ValidationError('CPF inválido. Os dígitos verificadores não conferem.')