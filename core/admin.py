from django.contrib import admin

from core.forms import EquipeUSFAdminForm
from core.models import (USF, Aviso, Cargo, CondicaoSaude, ConfiguracaoSistema, EquipeUSF, MicroArea, Paciente, PacienteCondicao, PerfilUsuario, TipoAtendimento)
# from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
# from django.contrib import admin

# from .models import (Cargo, ConfiguracaoSistema, CondicaoSaude,
#                      EquipeUSF, PacienteCondicao, PerfilUsuario, USF, 
#                      TipoAtendimento, Aviso, Paciente,
#                      AcompanhamentoCronico, MonitoramentoGestante)

def usuario_nome_completo(self):
    return self.get_full_name() or self.username

User.add_to_class("__str__", usuario_nome_completo)

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('nome_completo', 'cpf', 'nivel', 'ativo')
    list_filter = ('nivel', 'ativo')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'cpf')

    @admin.display(description='Nome Completo')
    def nome_completo(self, obj):
        # get_full_name() junta o first_name e o last_name com um espaço no meio
        nome = obj.user.get_full_name()
        
        # Se o nome estiver vazio (em utilizadores recém-criados), mostramos o username
        return nome if nome else obj.user.username

# # Inline para mostrar o CPF dentro da página do usuário
# class PerfilInline(admin.StackedInline):
#     model = PerfilUsuario
#     can_delete = False
#     verbose_name_plural = 'CPF de acesso'
# class UserAdmin(BaseUserAdmin):
#     inlines = [PerfilInline]


# admin.site.unregister(User)
# admin.site.register(User, UserAdmin)

@admin.register(USF)
class USFAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cnes', 'municipio', 'ativo')   # ATUALIZADO
    list_filter = ('ativo',)
    search_fields = ('nome', 'cnes', 'municipio')           # ATUALIZADO

@admin.register(TipoAtendimento)
class TipoAtendimentoAdmin(admin.ModelAdmin):
    list_display = ('atendimento', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('atendimento',)

@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'categoria', 'data_validade', 'ativo')
    list_filter = ('categoria', 'ativo')
    search_fields = ('titulo',)

@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome',)

@admin.register(EquipeUSF)
class EquipeUSFAdmin(admin.ModelAdmin):
    form = EquipeUSFAdminForm    
    list_display = ('nome_profissional', 'cargo', 'usf', 'ativo', 'data_entrada', 'data_saida')
    list_filter = ('usf', 'cargo', 'ativo')
    search_fields = ('user__first_name', 'user__last_name')
    
    @admin.display(description='Profissional')
    def nome_profissional(self, obj):
        return obj.user.get_full_name() or obj.user.username

@admin.register(MicroArea)
class MicroAreaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'usf', 'responsavel', 'ativo')
    list_filter = ('usf', 'ativo')
    search_fields = ('codigo',)

class PacienteCondicaoInline(admin.TabularInline):
    """
    Mostra as condições do paciente dentro da página do paciente
    no admin do Django — para consulta e correção rápida.
    """
    model = PacienteCondicao
    extra = 0
    fields = ('condicao', 'data_inicio', 'data_referencia', 'data_fim', 'observacao')

@admin.register(CondicaoSaude)
class CondicaoSaudeAdmin(admin.ModelAdmin):
    list_display = ('icone', 'nome', 'codigo', 'afeta_prioridade', 'ativo')
    list_filter  = ('afeta_prioridade', 'ativo')
    search_fields = ('nome', 'codigo')
    prepopulated_fields = {'codigo': ('nome',)}  # preenche o slug automaticamente

# Atualiza o PacienteAdmin para mostrar condições inline

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'usf', 'micro_area', 'cpf', 'cartao_sus', 'ativo', 'obito')
    list_filter   = ('usf', 'micro_area', 'sexo', 'ativo', 'obito')
    search_fields = ('nome', 'cpf', 'cartao_sus')
    inlines       = [PacienteCondicaoInline]
    exclude = ('cadastrado_por',)

    # 🌟 MÁGICA 3: Preenche o usuário automaticamente nos bastidores
    def save_model(self, request, obj, form, change):
        if not obj.pk: # Se for um paciente NOVO (ainda não salvo)
            obj.cadastrado_por = request.user # Preenche com quem está logado
        super().save_model(request, obj, form, change)

@admin.register(ConfiguracaoSistema)
class ConfiguracaoSistemaAdmin(admin.ModelAdmin):
    """
    Impede criação de mais de uma configuração —
    o sistema sempre usa só a de pk=1.
    """
    def has_add_permission(self, request):
        # Só permite adicionar se ainda não existir nenhuma
        return not ConfiguracaoSistema.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Não permite apagar — sempre tem que existir uma
        return False

# # ─── REGISTOS PARA VALIDAÇÃO DE IMPORTAÇÃO (E-SUS) ───────────────────────────

# @admin.register(MonitoramentoGestante)
# class MonitoramentoGestanteAdmin(admin.ModelAdmin):
#     """
#     Painel para verificar os dados importados das Gestantes.
#     """
#     # Define as colunas que aparecem na lista
#     list_display = ('paciente', 'ig_semanas', 'dpp', 'risco_gestacional', 'data_extracao_esus')
    
#     # Cria filtros laterais rápidos
#     list_filter = ('risco_gestacional', 'data_extracao_esus')
    
#     # Permite pesquisar pelo nome ou CPF da gestante
#     search_fields = ('paciente__nome', 'paciente__cpf')
    
#     # Organiza para mostrar as importações mais recentes primeiro
#     ordering = ('-data_extracao_esus',)

# @admin.register(AcompanhamentoCronico)
# class AcompanhamentoCronicoAdmin(admin.ModelAdmin):
#     """
#     Painel para verificar os dados de Diabéticos e Hipertensos.
#     """
#     # Define as colunas que aparecem na lista
#     list_display = ('paciente', 'ultima_consulta_medica', 'ultima_consulta_enfermagem', 'data_extracao_esus')
    
#     # Cria filtros laterais
#     list_filter = ('data_extracao_esus',)
    
#     # Permite pesquisar pelo nome ou CPF do paciente
#     search_fields = ('paciente__nome', 'paciente__cpf')
    
#     # Organiza para mostrar as importações mais recentes primeiro
#     ordering = ('-data_extracao_esus',)