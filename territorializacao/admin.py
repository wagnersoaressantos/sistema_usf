from django.contrib import admin
from .models import Logradouro, VinculoLogradouro, SentinelaRisco, FamiliaScore, FamiliaSentinela, MembroSentinela

class VinculoLogradouroInline(admin.TabularInline):
    model = VinculoLogradouro
    extra = 1

@admin.register(Logradouro)
class LogradouroAdmin(admin.ModelAdmin):
    list_display = ('logradouro', 'bairro', 'usf', 'ativo')
    list_filter = ('usf', 'ativo')
    search_fields = ('logradouro', 'bairro', 'cep')
    inlines = [VinculoLogradouroInline]

@admin.register(SentinelaRisco)
class SentinelaRiscoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'peso', 'ativo')
    list_filter = ('tipo', 'ativo')
    search_fields = ('nome', 'codigo')

class FamiliaSentinelaInline(admin.TabularInline):
    model = FamiliaSentinela
    extra = 1

class MembroSentinelaInline(admin.TabularInline):
    model = MembroSentinela
    extra = 1

@admin.register(FamiliaScore)
class FamiliaScoreAdmin(admin.ModelAdmin):
    list_display = ('nome_responsavel', 'cpf_responsavel', 'usf', 'score_total', 'classificacao')
    list_filter = ('classificacao', 'usf')
    search_fields = ('nome_responsavel', 'cpf_responsavel')
    inlines = [FamiliaSentinelaInline]