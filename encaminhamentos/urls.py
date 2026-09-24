from django.urls import path
from . import views

app_name = 'encaminhamentos'

urlpatterns = [
    # Dashboard e filas gerais
    path('', views.inicio, name='inicio'),
    path('fila/', views.lista_encaminhamentos, name='lista'),
    path('concluidos/', views.concluidos, name='concluidos'),
    
    # Ações
    path('novo/', views.cadastrar, name='cadastrar'),
    path('<int:pk>/', views.detalhe, name='detalhe'),

    # 🚀 FASE 7: ADMINISTRAÇÃO DA REGULAÇÃO (LINGUAGEM UBÍQUA)
    path('administracao/especialidades/', views.admin_tipos_enc, name='admin_tipos_enc'),
    
    path('administracao/categorias/nova/', views.admin_categoria_salvar, name='admin_categoria_criar'),
    path('administracao/categorias/<int:pk>/editar/', views.admin_categoria_salvar, name='admin_categoria_editar'),
    
    path('administracao/especialidades/nova/', views.admin_especialidade_salvar, name='admin_especialidade_criar'),
    path('administracao/especialidades/<int:pk>/editar/', views.admin_especialidade_salvar, name='admin_especialidade_editar'),
    
    path('administracao/cotas/', views.admin_cotas, name='admin_cotas'),
]