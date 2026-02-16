from django import forms
from .models import User, TokenCadastro, Escola, Turma

class ValidarTokenForm(forms.Form):
    codigo = forms.CharField(
        label="Código do Cartão", 
        widget=forms.TextInput(attrs={'class': 'form-control text-center text-uppercase form-control-lg', 'placeholder': 'KZ-XXXX-XXXX'})
    )

    def clean_codigo(self):
        codigo = self.cleaned_data['codigo'].strip().upper()
        
        try:
            token = TokenCadastro.objects.get(codigo=codigo, usado=False)
        except TokenCadastro.DoesNotExist:
            raise forms.ValidationError("Este código é inválido ou já foi ativado.")

        # --- REGRAS DE HIERARQUIA ---
        if token.tipo_usuario == 'ALUNO' and not token.turma:
            raise forms.ValidationError("Este cartão ainda não foi ativado pelo seu Professor. Aguarde a liberação.")
            
        if token.tipo_usuario == 'PROFESSOR' and not token.escola:
            raise forms.ValidationError("Este cartão de Professor ainda não foi vinculado a uma escola. Procure a direção.")
            
        if token.tipo_usuario == 'GESTOR_LOCAL' and not token.escola:
            raise forms.ValidationError("Este cartão de Gestor precisa estar vinculado a uma escola pelo Administrador.")

        return codigo

# 2. Formulário de Cadastro do Aluno (Hierárquico)
class RegistroUsuarioForm(forms.ModelForm):
    senha = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Crie uma senha segura'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu Nome'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu Sobrenome'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Crie seu usuário de acesso'}),
        }

class VincularCartoesForm(forms.Form):
    # Um campo grande para ele colar ou digitar vários códigos de uma vez (ex: com leitor de código de barras)
    codigos = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'KZ-1234-5678\nKZ-ABCD-EFGH\n...'}),
        help_text="Digite um código por linha."
    )
    turma = forms.ModelChoiceField(
        queryset=Turma.objects.none(), 
        empty_label="Selecione a Turma de destino",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        professor = kwargs.pop('professor', None)
        super().__init__(*args, **kwargs)
        if professor:
            # O professor só pode vincular cartões para as turmas dele (ou da escola dele)
            self.fields['turma'].queryset = Turma.objects.filter(escola__in=professor.escolas.all())