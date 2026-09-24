from django.urls import path, include
from . import views

app_name = 'core'

urlpatterns = [
    # Autenticação
    path('login/',  views.login_view,  name='login'),
    path('logout/', views.logout_view, name='logout'),

    # hub principal
    path('', views.hub, name='hub'),
    
    # Alternância de USF (O botão do menu superior)
    path('alternar-usf/<int:usf_id>/', views.alternar_usf, name='alternar_usf'),

    # Área de administração — estrutura base
    path('administracao/',                              views.painel_admin,            name='painel_admin'),

    # 🚀 Módulos do Sistema (NOVO)
    path('administracao/modulos/',                      views.admin_modulos,           name='admin_modulos'),
    path('administracao/modulos/novo/',                 views.admin_modulo_salvar,     name='admin_modulo_criar'),
    path('administracao/modulos/<int:pk>/',             views.admin_modulo_salvar,     name='admin_modulo_editar'),

    # Usuários
    path('administracao/usuarios/',                     views.admin_usuarios,          name='admin_usuarios'),
    path('administracao/usuarios/novo/',                views.admin_usuario_criar,     name='admin_usuario_criar'),
    path('administracao/usuarios/<int:pk>/',            views.admin_usuario_editar,    name='admin_usuario_editar'),

    # USFs
    path('administracao/usfs/',                         views.admin_usfs,              name='admin_usfs'),
    path('administracao/usfs/novo/',                    views.admin_usf_salvar,        name='admin_usf_criar'),
    path('administracao/usfs/<int:pk>/',                views.admin_usf_salvar,        name='admin_usf_editar'),

    # Equipe da USF
    path('administracao/equipe/',                       views.admin_equipe,            name='admin_equipe'),
    path('administracao/equipe/novo/',                  views.admin_equipe_salvar,     name='admin_equipe_criar'),
    path('administracao/equipe/<int:pk>/',              views.admin_equipe_salvar,     name='admin_equipe_editar'),
    path('administracao/equipe/<int:pk>/desativar/',    views.admin_equipe_desativar,  name='admin_equipe_desativar'),

    # Cargos
    path('administracao/cargos/',                       views.admin_cargos,            name='admin_cargos'),
    path('administracao/cargos/novo/',                  views.admin_cargo_salvar,      name='admin_cargo_criar'),
    path('administracao/cargos/<int:pk>/',              views.admin_cargo_salvar,      name='admin_cargo_editar'),

    # Micro-áreas
    path('administracao/microareas/',                   views.admin_microareas,        name='admin_microareas'),
    path('administracao/microareas/novo/',              views.admin_microarea_salvar,  name='admin_microarea_criar'),
    path('administracao/microareas/<int:pk>/',          views.admin_microarea_salvar,  name='admin_microarea_editar'),

    # Pacientes
    path('administracao/pacientes/',                    views.admin_pacientes,                     name='admin_pacientes'),
    path('administracao/pacientes/novo/',               views.admin_paciente_salvar,               name='admin_paciente_criar'),
    path('administracao/pacientes/<int:pk>/',           views.admin_paciente_salvar,               name='admin_paciente_editar'),
    path('administracao/pacientes/inativar/',           views.admin_pacientes_inativar,            name='admin_pacientes_inativar'),
    path('administracao/pacientes/inativar/confirmar/', views.admin_pacientes_inativar_confirmar,  name='admin_pacientes_inativar_confirmar'),
    path('administracao/importar-pacientes/',           views.importar_pacientes,                  name='importar_pacientes'),
    path('administracao/importar-condicoes/',           views.importar_condicoes,                  name='importar_condicoes'),
    path('administracao/importar-territorio/',          views.importar_territorio,                 name='importar_territorio'),
    
    # Tipos de atendimento
    path('administracao/tipos/',                        views.admin_tipos,             name='admin_tipos'),
    path('administracao/tipos/novo/',                   views.admin_tipo_salvar,       name='admin_tipo_criar'),
    path('administracao/tipos/<int:pk>/',               views.admin_tipo_salvar,       name='admin_tipo_editar'),

    # Avisos
    path('administracao/avisos/',                       views.admin_avisos,            name='admin_avisos'),
    path('administracao/avisos/novo/',                  views.admin_aviso_salvar,      name='admin_aviso_criar'),
    path('administracao/avisos/<int:pk>/',              views.admin_aviso_salvar,      name='admin_aviso_editar'),
    path('administracao/avisos/<int:pk>/excluir/',      views.admin_aviso_excluir,     name='admin_aviso_excluir'),

    # Sentinelas de risco
    path('administracao/sentinelas/',          views.admin_sentinelas,       name='admin_sentinelas'),
    path('administracao/sentinelas/novo/',     views.admin_sentinela_salvar, name='admin_sentinela_criar'),
    path('administracao/sentinelas/<int:pk>/', views.admin_sentinela_salvar, name='admin_sentinela_editar'),

    # Condições de saúde
    path('administracao/condicoes/',          views.admin_condicoes,       name='admin_condicoes'),
    path('administracao/condicoes/novo/',     views.admin_condicao_salvar, name='admin_condicao_criar'),
    path('administracao/condicoes/<int:pk>/', views.admin_condicao_salvar, name='admin_condicao_editar'),

    # Manutenção do sistema/atualização via git pull
    path('manutencao/atualizar-git/', views.executar_git_pull, name='executar_git_pull'),
]