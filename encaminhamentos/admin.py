from django.contrib import admin
# Repare que o HistoricoFamiliar já não está no import abaixo!
from .models import Subcategoria, TipoEncaminhamento, ConfigCota, ConfigCotaSubcategoria, RegraCondicao, Encaminhamento

class ConfigCotaSubcategoriaInline(admin.TabularInline):
    model = ConfigCotaSubcategoria
    extra = 1

@admin.register(Subcategoria)
class SubcategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cota_padrao', 'ativo')
    search_fields = ('nome',)
    inlines = [ConfigCotaSubcategoriaInline]

class RegraCondicaoInline(admin.TabularInline):
    model = RegraCondicao
    extra = 1

class ConfigCotaInline(admin.TabularInline):
    model = ConfigCota
    extra = 1

@admin.register(TipoEncaminhamento)
class TipoEncaminhamentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'subcategoria', 'cota_padrao', 'ativo')
    list_filter = ('subcategoria', 'ativo')
    search_fields = ('nome',)
    inlines = [RegraCondicaoInline, ConfigCotaInline]

@admin.register(Encaminhamento)
class EncaminhamentoAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'tipo', 'usf', 'status', 'prioridade', 'data_solicitacao')
    list_filter = ('status', 'prioridade', 'usf', 'tipo__subcategoria')
    search_fields = ('paciente__nome', 'paciente__cpf', 'tipo__nome')
    exclude = ('solicitado_por',)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.solicitado_por = request.user
        super().save_model(request, obj, form, change)