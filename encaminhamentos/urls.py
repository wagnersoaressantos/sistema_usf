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
]