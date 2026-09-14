from django.contrib import admin
from django.contrib.auth.models import User

from .models import (
    PerfilUsuario, USF, TipoAtendimento, Aviso, Cargo, 
    ModuloSistema, EquipeUSF, MicroArea, Paciente, CondicaoSaude, PacienteCondicao
)

# Faz o Django mostrar o Nome Completo em todos os 'selects' de usuários
def usuario_nome_completo(self):
    return self.get_full_name() or self.username
User.add_to_class("__str__", usuario_nome_completo)

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'cpf', 'nivel', 'ativo')
    search_fields = ('user__first_name', 'cpf')
    list_filter = ('nivel', 'ativo')

@admin.register(USF)
class USFAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cnes', 'municipio', 'ativo')

@admin.register(TipoAtendimento)
class TipoAtendimentoAdmin(admin.ModelAdmin):
    list_display = ('atendimento', 'ativo')

@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'categoria', 'data_validade', 'ativo')

@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo')

@admin.register(ModuloSistema)
class ModuloSistemaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug_app', 'ativo', 'ordem')
    list_editable = ('ativo', 'ordem') # Permite ligar/desligar com 1 clique!
    search_fields = ('nome', 'slug_app')

@admin.register(EquipeUSF)
class EquipeUSFAdmin(admin.ModelAdmin):
    list_display = ('user', 'cargo', 'usf', 'ativo')
    list_filter = ('usf', 'cargo', 'ativo')
    search_fields = ('user__first_name', 'user__last_name')

@admin.register(MicroArea)
class MicroAreaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'usf', 'responsavel', 'ativo')
    list_filter = ('usf', 'ativo')

class PacienteCondicaoInline(admin.TabularInline):
    model = PacienteCondicao
    extra = 1

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'usf', 'cpf', 'cartao_sus', 'ativo', 'obito')
    list_filter   = ('usf', 'sexo', 'ativo', 'obito')
    search_fields = ('nome', 'cpf', 'cartao_sus')
    inlines       = [PacienteCondicaoInline]
    
    # Esconde o campo da tela do usuário
    exclude = ('cadastrado_por',)

    # Preenche o usuário automaticamente nos bastidores
    def save_model(self, request, obj, form, change):
        if not obj.pk: # Se for um paciente NOVO (ainda não salvo)
            obj.cadastrado_por = request.user # Preenche com quem está logado
        super().save_model(request, obj, form, change)

@admin.register(CondicaoSaude)
class CondicaoSaudeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'codigo', 'afeta_prioridade', 'ativo')