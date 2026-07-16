from django.core.exceptions import ValidationError


def validate_cedula_ec(value):
    """Validates Ecuadorian cedula (10 digits) or RUC (13 digits)."""
    value = str(value).strip()
    if not value.isdigit():
        raise ValidationError('La cédula/RUC solo debe contener dígitos.')
    if len(value) not in (10, 13):
        raise ValidationError('La cédula debe tener 10 dígitos o el RUC 13 dígitos.')

    if len(value) == 10 or (len(value) == 13 and value[10:] == '001'):
        coefficients = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        total = 0
        for i, coef in enumerate(coefficients):
            digit = int(value[i]) * coef
            if digit >= 10:
                digit -= 9
            total += digit
        verifier = (10 - (total % 10)) % 10
        if verifier != int(value[9]):
            raise ValidationError('La cédula ingresada no es válida.')
