from django import forms
from .models import User, TokenCadastro, Escola, Turma

# 1. Formulário só para digitar o código
class ValidarTokenForm(forms.Form):
    codigo = forms.CharField(
        label="Código de Acesso",
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center text-uppercase', 
            'placeholder': 'KZ-XXXX-XXXX',
            'style': 'letter-spacing: 3px; font-weight: bold;'
        })
    )

    def clean_codigo(self):
        codigo = self.cleaned_data['codigo'].strip().upper()
        # Verifica se existe e se não foi usado
        if not TokenCadastro.objects.filter(codigo=codigo, usado=False).exists():
            raise forms.ValidationError("Este código é inválido ou já foi utilizado.")
        return codigo

# 2. Formulário de Cadastro do Aluno (Hierárquico)
class RegistroAlunoForm(forms.ModelForm):
    escola = forms.ModelChoiceField(
        queryset=Escola.objects.all(),
        empty_label="Selecione sua Escola",
        widget=forms.Select(attrs={'class': 'form-control form-select'})
    )
    # A turma começa vazia, será preenchida via Javascript (AJAX) ou recarga
    turma = forms.ModelChoiceField(
        queryset=Turma.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control form-select'})
    )
    senha = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email']
        # Adicione widgets para ficar bonito...

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Lógica para popular o dropdown de turmas se a escola for selecionada
        if 'escola' in self.data:
            try:
                escola_id = int(self.data.get('escola'))
                self.fields['turma'].queryset = Turma.objects.filter(escola_id=escola_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            # Caso de edição (menos provável aqui)
            self.fields['turma'].queryset = self.instance.turmas.all()