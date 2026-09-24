from django.urls import path
from . import views

app_name = 'territorializacao'

urlpatterns = [
    # Famílias e Score de Risco
    path('familias/', views.familias_score, name='familias_score'),
    path('familias/<str:cpf_responsavel>/', views.familia_detalhe, name='familia_detalhe'),
    
    # Mapa de Ruas (Logradouros)
    path('ruas/', views.territorio_lista, name='territorio_lista'),
    path('ruas/nova/', views.admin_rua_salvar, name='admin_rua_criar'),
    path('ruas/<int:pk>/editar/', views.admin_rua_salvar, name='admin_rua_editar'),

    # 🚀 Fichas SSA2
    path('ssa2/', views.painel_ssa2, name='painel_ssa2'),
    path('ssa2/preencher/<int:microarea_id>/', views.ficha_ssa2_preencher, name='ficha_ssa2_preencher'),
    path('ssa2/carga/', views.carga_geral_ssa2, name='carga_geral_ssa2'),
    path('ssa2/consolidado/', views.consolidado_geral_ssa2, name='consolidado_geral_ssa2'),
]