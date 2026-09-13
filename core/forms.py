from django import forms
from core.models import EquipeUSF


def limpar_cpf(cpf):
    return ''.join(c for c in cpf if c.isdigit())


class LoginForm(forms.Form):
    cpf = forms.CharField(
        label='CPF', max_length=14,
        widget=forms.TextInput(attrs={
            'placeholder': '000.000.000-00',
            'autofocus': True,
            'class': 'form-input',
        })
    )
    senha = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'class': 'form-input'})
    )

    def clean_cpf(self):
        return limpar_cpf(self.cleaned_data['cpf'])
    
class EquipeUSFAdminForm(forms.ModelForm):
    """
    Form personalizado para mostrar nome completo
    no select de usuário em vez do username.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].label_from_instance = lambda obj: (
            obj.get_full_name() or obj.username
        )

    class Meta:
        model = EquipeUSF
        fields = '__all__'    