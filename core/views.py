from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError

import subprocess
import csv
import io
from datetime import datetime, date, timedelta

# Repare que ConfiguracaoSistema não está mais aqui!
from core.models import (Cargo, CondicaoSaude, EquipeUSF, HistoricoFamiliar, Paciente, PacienteCondicao, 
                         PerfilUsuario, USF, TipoAtendimento, Aviso, MicroArea, ModuloSistema)

from core.decorators import admin_required
from core.forms import LoginForm
from core.validators import validar_cpf
from django.apps import apps


# ─── LOGIN & LOGOUT ───────────────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect(request.GET.get('next', 'core:hub'))

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cpf = form.cleaned_data['cpf']
        senha = form.cleaned_data['senha']
        user = authenticate(request, username=cpf, password=senha)
        if user:
            login(request, user)
            return redirect(request.GET.get('next', 'core:hub'))
        else:
            messages.error(request, 'CPF ou senha inválidos.')
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('core:login')

# ─── HUB ───────────────────────────────────────────────────────────────────
@login_required
def hub(request):
    usf = None
    cargo = None
    vinculo = EquipeUSF.objects.filter(
        user=request.user, ativo=True
    ).select_related('usf').first()
    
    if vinculo:
        usf = vinculo.usf
        cargo = vinculo.cargo.nome

    hoje   = date.today()

    # MÁGICA DOS MÓDULOS: Descobre quais apps o Admin ligou no painel
    modulos_ativos_db = list(ModuloSistema.objects.filter(ativo=True).values_list('slug_app', flat=True))

    total_fila       = 0
    total_duplicatas = 0
    retornos_mes     = []
    retornos_proximo = []

    # Verifica se "encaminhamentos" está ligado E instalado fisicamente
    encaminhamentos_visivel = 'encaminhamentos' in modulos_ativos_db and apps.is_installed('encaminhamentos')

    if encaminhamentos_visivel and usf:
        Encaminhamento = apps.get_model('encaminhamentos', 'Encaminhamento')
        total_fila = Encaminhamento.objects.filter(usf=usf, status__in=['aguardando', 'regulacao', 'upae']).count()
        total_duplicatas = Encaminhamento.objects.filter(usf=usf, duplicata_de__isnull=False, status__in=['aguardando', 'regulacao', 'upae']).count()
        retornos_mes = list(Encaminhamento.objects.filter(usf=usf, prioridade=1, status__in=['aguardando', 'regulacao', 'upae'], mes_retorno=hoje.month, ano_retorno=hoje.year).select_related('paciente', 'tipo').order_by('data_solicitacao'))
        proximo_mes = hoje.month + 1 if hoje.month < 12 else 1
        proximo_ano = hoje.year if hoje.month < 12 else hoje.year + 1
        retornos_proximo = list(Encaminhamento.objects.filter(usf=usf, prioridade=1, status__in=['aguardando', 'regulacao', 'upae'], mes_retorno=proximo_mes, ano_retorno=proximo_ano).select_related('paciente', 'tipo').order_by('data_solicitacao'))

    total_mutirao = 0
    mutirao_visivel = 'mutirao' in modulos_ativos_db and apps.is_installed('mutirao')
    if mutirao_visivel:
        Atendimento = apps.get_model('mutirao', 'Atendimento')
        total_mutirao = Atendimento.objects.count()

    return render(request, 'hub.html', {
        'usf':              usf,
        'cargo':            cargo,
        'encaminhamentos_visivel': encaminhamentos_visivel,
        'total_fila':       total_fila,
        'total_duplicatas': total_duplicatas,
        'mutirao_visivel':  mutirao_visivel,
        'total_mutirao':    total_mutirao,
        'retornos_mes':     retornos_mes,
        'retornos_proximo': retornos_proximo,
        'hoje':             hoje,
    })

def erro_404(request, exception):
    return render(request, '404.html', status=404)

# ─── ALTERNAR USF (MULTI-TENANCY) ─────────────────────────────────────────────
@login_required
def alternar_usf(request, usf_id):
    """Muda a USF ativa do utilizador na sessão atual e recarrega a página."""
    if request.method == 'POST' and hasattr(request.user, 'perfil'):
        perfil = request.user.perfil
        is_master = perfil.is_master
        
        # Verifica se a USF existe
        usf = get_object_or_404(USF, pk=usf_id, ativo=True)
        
        # Verifica se ele tem permissão para aceder a esta USF (se não for Master)
        tem_permissao = False
        if is_master:
            tem_permissao = True
        else:
            tem_permissao = EquipeUSF.objects.filter(user=request.user, usf=usf, ativo=True).exists()
        
        if tem_permissao:
            # MAGIA: Guarda a escolha no perfil!
            perfil.usf_ativa_padrao = usf
            perfil.save()
            messages.success(request, f'Unidade alterada para {usf.nome}!')
        else:
            messages.error(request, 'Você não tem permissão para aceder a esta unidade.')
            
    # Redireciona de volta para a página onde ele estava (ou para o Hub se falhar)
    next_url = request.META.get('HTTP_REFERER', reverse('core:hub'))
    return redirect(next_url)


# ════════════════════════════════════════════════════════
# ÁREA DE ADMINISTRAÇÃO
# ════════════════════════════════════════════════════════

@admin_required
def painel_admin(request):
    total_microareas = 0
    if apps.is_installed('territorializacao'):
        from territorializacao.models import MicroArea as TerMicroArea
        total_microareas = TerMicroArea.objects.count()

    contexto = {
        'total_usuarios':  PerfilUsuario.objects.filter(ativo=True).count(),
        'total_inativos':  PerfilUsuario.objects.filter(ativo=False).count(),
        'total_usfs':      USF.objects.count(),
        'total_tipos':     TipoAtendimento.objects.count(),
        'total_equipe':    EquipeUSF.objects.filter(ativo=True).count(),
        'total_cargos':    Cargo.objects.count(),
        'total_microareas': total_microareas,
        'total_pacientes': Paciente.objects.count(),
        'total_tipos_enc': 0,
        'total_cotas':     0,
    }
    
    if apps.is_installed('encaminhamentos'):
        TipoEncaminhamento = apps.get_model('encaminhamentos', 'TipoEncaminhamento')
        ConfigCota = apps.get_model('encaminhamentos', 'ConfigCota')
        contexto['total_tipos_enc'] = TipoEncaminhamento.objects.filter(ativo=True).count()
        contexto['total_cotas'] = ConfigCota.objects.count()
        
    return render(request, 'core/admin/painel.html', contexto)

@admin_required
def admin_usuarios(request):
    perfis = PerfilUsuario.objects.select_related('user').all().order_by('user__first_name')
    return render(request, 'core/admin/usuarios.html', {'perfis': perfis})

@admin_required
def admin_usuario_criar(request):
    if request.method == 'POST':
        nome      = request.POST.get('nome', '').strip()
        sobrenome = request.POST.get('sobrenome', '').strip()
        cpf       = ''.join(c for c in request.POST.get('cpf', '') if c.isdigit())
        senha     = request.POST.get('senha', '')
        nivel     = request.POST.get('nivel', 'comum')
        ativo     = request.POST.get('ativo') == 'on'

        cpf_valido = True
        mensagem_erro_cpf = ''
        try: validar_cpf(cpf)
        except ValidationError as e:
            cpf_valido = False
            mensagem_erro_cpf = e.message

        if not nome or not cpf or not senha: messages.error(request, 'Nome, CPF e senha são obrigatórios.')
        elif not cpf_valido: messages.error(request, mensagem_erro_cpf)
        elif PerfilUsuario.objects.filter(cpf=cpf).exists(): messages.error(request, f'Já existe um utilizador com o CPF {cpf}.')
        elif len(senha) < 6: messages.error(request, 'A senha deve ter pelo menos 6 caracteres.')
        else:
            user = User.objects.create_user(username=f'user_{cpf}', password=senha, first_name=nome, last_name=sobrenome)
            PerfilUsuario.objects.create(user=user, cpf=cpf, nivel=nivel, ativo=ativo)
            messages.success(request, f'Utilizador {nome} criado com sucesso!')
            return redirect('core:admin_usuarios')

    return render(request, 'core/admin/usuario_form.html', {'titulo': 'Novo utilizador', 'acao': 'Criar utilizador'})

@admin_required
def admin_usuario_editar(request, pk):
    perfil = get_object_or_404(PerfilUsuario, pk=pk)
    user   = perfil.user
    if request.method == 'POST':
        nome       = request.POST.get('nome', '').strip()
        sobrenome  = request.POST.get('sobrenome', '').strip()
        cpf        = ''.join(c for c in request.POST.get('cpf', '') if c.isdigit())
        nivel      = request.POST.get('nivel', 'comum')
        ativo      = request.POST.get('ativo') == 'on'
        nova_senha = request.POST.get('senha', '').strip()

        cpf_valido = True
        mensagem_erro_cpf = ''
        try: validar_cpf(cpf)
        except ValidationError as e:
            cpf_valido = False
            mensagem_erro_cpf = e.message

        if not cpf_valido: messages.error(request, mensagem_erro_cpf)
        elif PerfilUsuario.objects.filter(cpf=cpf).exclude(pk=pk).exists(): messages.error(request, f'Já existe outro utilizador com o CPF {cpf}.')
        else:
            user.first_name = nome
            user.last_name  = sobrenome
            user.save()
            perfil.cpf   = cpf
            perfil.nivel = nivel
            perfil.ativo = ativo
            perfil.save()
            if nova_senha:
                if len(nova_senha) < 6:
                    messages.error(request, 'A nova senha deve ter pelo menos 6 caracteres.')
                    return render(request, 'core/admin/usuario_form.html', {'titulo': 'Editar utilizador', 'acao': 'Salvar alterações', 'perfil': perfil})
                user.set_password(nova_senha)
                user.save()
                messages.success(request, f'Utilizador {nome} atualizado e senha redefinida!')
            else:
                messages.success(request, f'Utilizador {nome} atualizado com sucesso!')
            return redirect('core:admin_usuarios')

    return render(request, 'core/admin/usuario_form.html', {'titulo': 'Editar utilizador', 'acao': 'Salvar alterações', 'perfil': perfil})

@admin_required
def admin_usfs(request):
    usfs = USF.objects.all().order_by('nome')
    return render(request, 'core/admin/usfs.html', {'usfs': usfs})

@admin_required
def admin_usf_salvar(request, pk=None):
    usf = get_object_or_404(USF, pk=pk) if pk else None
    if request.method == 'POST':
        nome  = request.POST.get('nome', '').strip()
        cnes  = request.POST.get('cnes', '').strip() or None
        municipio = request.POST.get('municipio', '').strip()        
        ativo = request.POST.get('ativo') == 'on'

        if not nome: messages.error(request, 'O nome da USF é obrigatório.')
        elif USF.objects.filter(nome=nome).exclude(pk=pk).exists(): messages.error(request, f'Já existe uma USF com o nome "{nome}".')
        else:
            if usf:
                usf.nome = nome; usf.cnes = cnes; usf.municipio = municipio; usf.ativo = ativo; usf.save()
                messages.success(request, f'USF "{nome}" atualizada!')
            else:
                USF.objects.create(nome=nome, cnes=cnes, municipio=municipio, ativo=ativo)
                messages.success(request, f'USF "{nome}" criada!')
            return redirect('core:admin_usfs')
    return render(request, 'core/admin/usf_form.html', {'usf': usf, 'titulo': 'Editar USF' if usf else 'Nova USF', 'acao': 'Salvar alterações' if usf else 'Criar USF'})

@admin_required
def admin_tipos(request):
    tipos = TipoAtendimento.objects.all().order_by('atendimento')
    return render(request, 'core/admin/tipos.html', {'tipos': tipos})

@admin_required
def admin_tipo_salvar(request, pk=None):
    tipo = get_object_or_404(TipoAtendimento, pk=pk) if pk else None
    if request.method == 'POST':
        nome  = request.POST.get('nome', '').strip()
        ativo = request.POST.get('ativo') == 'on'
        if not nome: messages.error(request, 'O nome do tipo é obrigatório.')
        elif TipoAtendimento.objects.filter(atendimento=nome).exclude(pk=pk).exists(): messages.error(request, f'Já existe um tipo com o nome "{nome}".')
        else:
            if tipo:
                tipo.atendimento = nome; tipo.ativo = ativo; tipo.save()
                messages.success(request, f'Tipo "{nome}" atualizado!')
            else:
                TipoAtendimento.objects.create(atendimento=nome, ativo=ativo) 
                messages.success(request, f'Tipo "{nome}" criado!')
            return redirect('core:admin_tipos')
    return render(request, 'core/admin/tipo_form.html', {'tipo': tipo, 'titulo': 'Editar tipo' if tipo else 'Novo tipo', 'acao': 'Salvar alterações' if tipo else 'Criar tipo'})

@admin_required
def admin_avisos(request):
    avisos = Aviso.objects.all()
    hoje   = timezone.now().date()
    return render(request, 'core/admin/avisos.html', {'avisos': avisos, 'hoje': hoje})

@admin_required
def admin_aviso_salvar(request, pk=None):
    aviso = get_object_or_404(Aviso, pk=pk) if pk else None
    if request.method == 'POST':
        titulo    = request.POST.get('titulo', '').strip()
        mensagem  = request.POST.get('mensagem', '').strip()
        categoria = request.POST.get('categoria', 'aviso')
        validade  = request.POST.get('data_validade', '')
        ativo     = request.POST.get('ativo') == 'on'

        if not titulo or not mensagem or not validade:
            messages.error(request, 'Título, mensagem e validade são obrigatórios.')
        else:
            from datetime import date
            try: data_validade = date.fromisoformat(validade)
            except ValueError:
                messages.error(request, 'Data de validade inválida.')
                return render(request, 'core/admin/aviso_form.html', {'aviso': aviso, 'titulo': 'Editar aviso' if aviso else 'Novo aviso', 'acao': 'Salvar alterações' if aviso else 'Criar aviso', 'categorias': Aviso.CATEGORIAS})

            if aviso:
                aviso.titulo = titulo; aviso.mensagem = mensagem; aviso.categoria = categoria; aviso.data_validade = data_validade; aviso.ativo = ativo; aviso.save()
                messages.success(request, f'Aviso "{titulo}" atualizado!')
            else:
                Aviso.objects.create(titulo=titulo, mensagem=mensagem, categoria=categoria, data_validade=data_validade, ativo=ativo)
                messages.success(request, f'Aviso "{titulo}" criado!')
            return redirect('core:admin_avisos')
    return render(request, 'core/admin/aviso_form.html', {'aviso': aviso, 'titulo': 'Editar aviso' if aviso else 'Novo aviso', 'acao': 'Salvar alterações' if aviso else 'Criar aviso', 'categorias': Aviso.CATEGORIAS})

@admin_required
def admin_aviso_excluir(request, pk):
    aviso = get_object_or_404(Aviso, pk=pk)
    if request.method == 'POST':
        aviso.delete()
        messages.success(request, 'Aviso excluído.')
        return redirect('core:admin_avisos')
    return render(request, 'core/admin/aviso_excluir.html', {'aviso': aviso})

@admin_required
def admin_equipe(request):
    equipe = EquipeUSF.objects.select_related('user', 'cargo', 'usf').order_by('usf', 'cargo__nome', 'user__first_name')
    return render(request, 'core/admin/equipe.html', {'equipe': equipe})

@admin_required
def admin_equipe_salvar(request, pk=None):
    vinculo = get_object_or_404(EquipeUSF, pk=pk) if pk else None
    if request.method == 'POST':
        user_id = request.POST.get('user'); usf_id = request.POST.get('usf'); cargo_id = request.POST.get('cargo')
        ativo = request.POST.get('ativo') == 'on'; data_entrada = request.POST.get('data_entrada') or None; data_saida = request.POST.get('data_saida') or None
        if not user_id or not usf_id or not cargo_id: messages.error(request, 'Profissional, USF e cargo são obrigatórios.')
        else:
            if vinculo:
                vinculo.user_id = user_id; vinculo.usf_id = usf_id; vinculo.cargo_id = cargo_id; vinculo.ativo = ativo; vinculo.data_entrada = data_entrada; vinculo.data_saida = data_saida; vinculo.save()
                messages.success(request, 'Vínculo atualizado!')
            else:
                EquipeUSF.objects.create(user_id=user_id, usf_id=usf_id, cargo_id=cargo_id, ativo=ativo, data_entrada=data_entrada, data_saida=data_saida)
                messages.success(request, 'Membro adicionado à equipa!')
            return redirect('core:admin_equipe')
    usuarios = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    usfs = USF.objects.filter(ativo=True)
    cargos = Cargo.objects.filter(ativo=True)
    return render(request, 'core/admin/equipe_form.html', {'vinculo': vinculo, 'usuarios': usuarios, 'usfs': usfs, 'cargos': cargos, 'titulo': 'Editar vínculo' if vinculo else 'Novo membro', 'acao': 'Salvar alterações' if vinculo else 'Adicionar à equipa'})

@admin_required
def admin_equipe_desativar(request, pk):
    vinculo = get_object_or_404(EquipeUSF, pk=pk)
    if request.method == 'POST':
        vinculo.ativo = False
        vinculo.save()
        messages.success(request, f'Vínculo de {vinculo.user.get_full_name()} desativado.')
        return redirect('core:admin_equipe')
    return render(request, 'core/admin/equipe_desativar.html', {'vinculo': vinculo})

@admin_required
def admin_cargos(request):
    cargos = Cargo.objects.all().order_by('nome')
    return render(request, 'core/admin/cargos.html', {'cargos': cargos})

@admin_required
def admin_cargo_salvar(request, pk=None):
    cargo = get_object_or_404(Cargo, pk=pk) if pk else None
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip(); ativo = request.POST.get('ativo') == 'on'
        if not nome: messages.error(request, 'O nome do cargo é obrigatório.')
        elif Cargo.objects.filter(nome=nome).exclude(pk=pk).exists(): messages.error(request, f'Já existe um cargo com o nome "{nome}".')
        else:
            if cargo: cargo.nome = nome; cargo.ativo = ativo; cargo.save(); messages.success(request, f'Cargo "{nome}" atualizado!')
            else: Cargo.objects.create(nome=nome, ativo=ativo); messages.success(request, f'Cargo "{nome}" criado!')
            return redirect('core:admin_cargos')
    return render(request, 'core/admin/cargo_form.html', {'cargo': cargo, 'titulo': 'Editar cargo' if cargo else 'Novo cargo', 'acao': 'Salvar alterações' if cargo else 'Criar cargo'})

@admin_required
def admin_microareas(request):
    microareas = MicroArea.objects.select_related('usf', 'responsavel__user', 'responsavel__cargo').order_by('usf', 'codigo')
    return render(request, 'core/admin/microareas.html', {'microareas': microareas})

@admin_required
def admin_microarea_salvar(request, pk=None):
    microarea = get_object_or_404(MicroArea, pk=pk) if pk else None
    if request.method == 'POST':
        usf_id = request.POST.get('usf'); codigo = request.POST.get('codigo', '').strip(); responsavel_id = request.POST.get('responsavel') or None; ativo = request.POST.get('ativo') == 'on'
        if not usf_id or not codigo: messages.error(request, 'USF e código são obrigatórios.')
        elif MicroArea.objects.filter(codigo=codigo).exclude(pk=pk).exists(): messages.error(request, f'Já existe uma micro-área com o código "{codigo}".')
        else:
            if microarea: microarea.usf_id = usf_id; microarea.codigo = codigo; microarea.responsavel_id = responsavel_id; microarea.ativo = ativo; microarea.save(); messages.success(request, f'Micro-área "{codigo}" atualizada!')
            else: MicroArea.objects.create(usf_id=usf_id, codigo=codigo, responsavel_id=responsavel_id, ativo=ativo); messages.success(request, f'Micro-área "{codigo}" criada!')
            return redirect('core:admin_microareas')
    usfs = USF.objects.filter(ativo=True)
    responsaveis = EquipeUSF.objects.filter(ativo=True).select_related('user', 'cargo', 'usf')
    return render(request, 'core/admin/microarea_form.html', {'microarea': microarea, 'usfs': usfs, 'responsaveis': responsaveis, 'titulo': 'Editar micro-área' if microarea else 'Nova micro-área', 'acao': 'Salvar alterações' if microarea else 'Criar micro-área'})

@admin_required
def admin_pacientes(request):
    q = request.GET.get('q', '').strip()
    microarea_filtro = request.GET.get('microarea', '')
    situacao_filtro  = request.GET.get('situacao', '')
    condicao_filtro  = request.GET.get('condicao', '')
    familia_filtro   = request.GET.get('familia', '')
    pagina           = request.GET.get('pagina', 1)

    pacientes = Paciente.objects.select_related('usf', 'micro_area').prefetch_related('condicoes__condicao').order_by('nome')

    if microarea_filtro == 'fora': pacientes = pacientes.filter(micro_area__isnull=True)
    elif microarea_filtro: pacientes = pacientes.filter(micro_area_id=microarea_filtro)

    if situacao_filtro == 'obito': pacientes = pacientes.filter(obito=True)
    elif situacao_filtro == 'inativo': pacientes = pacientes.filter(ativo=False, obito=False)
    elif situacao_filtro == 'ativo': pacientes = pacientes.filter(ativo=True, obito=False)

    if condicao_filtro: pacientes = pacientes.filter(condicoes__condicao__codigo=condicao_filtro, condicoes__data_fim__isnull=True).distinct()
    if familia_filtro: pacientes = pacientes.filter(cpf_responsavel=familia_filtro)
    if q: pacientes = pacientes.filter(Q(nome__icontains=q) | Q(cpf__icontains=q) | Q(cartao_sus__icontains=q))

    paginador = Paginator(pacientes, 50)
    try: pagina_atual = paginador.page(pagina)
    except Exception: pagina_atual = paginador.page(1)

    microareas = MicroArea.objects.filter(ativo=True).select_related('responsavel__user').order_by('codigo')
    condicoes = CondicaoSaude.objects.filter(ativo=True).order_by('nome')
    nome_familia = ''
    if familia_filtro:
        responsavel = Paciente.objects.filter(cpf_responsavel=familia_filtro, responsavel_familiar=True).first()
        if responsavel: nome_familia = responsavel.nome

    return render(request, 'core/pacientes/lista.html', {'pacientes': pagina_atual, 'microareas': microareas, 'condicoes': condicoes, 'q': q, 'microarea_filtro': microarea_filtro, 'situacao_filtro': situacao_filtro, 'condicao_filtro': condicao_filtro, 'familia_filtro': familia_filtro, 'nome_familia': nome_familia, 'total': paginador.count, 'num_paginas': paginador.num_pages})

@admin_required
def admin_paciente_salvar(request, pk=None):
    paciente = get_object_or_404(Paciente, pk=pk) if pk else None
    
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip(); cpf = ''.join(c for c in request.POST.get('cpf', '') if c.isdigit()) or None
        cartao_sus = request.POST.get('cartao_sus', '').strip() or None; data_nasc = request.POST.get('data_nascimento') or None
        sexo = request.POST.get('sexo', 'I'); telefone = request.POST.get('telefone', '').strip()
        endereco = request.POST.get('endereco', '').strip(); numero = request.POST.get('numero', '').strip()
        usf_id = request.POST.get('usf'); microarea_id = request.POST.get('micro_area') or None
        ativo = request.POST.get('ativo') == 'on'; obito = request.POST.get('obito') == 'on'; data_obito = request.POST.get('data_obito') or None
        condicoes_ids = request.POST.getlist('condicoes'); data_prevista_parto = request.POST.get('data_prevista_parto') or None

        cpf_valido = True; mensagem_erro_cpf = ''
        if cpf:
            try: validar_cpf(cpf)
            except ValidationError as e: cpf_valido = False; mensagem_erro_cpf = e.message

        if not nome or not usf_id: messages.error(request, 'Nome e USF são obrigatórios.')
        elif not cpf and not cartao_sus: messages.error(request, 'Informe o CPF ou o Cartão SUS.')
        elif not cpf_valido: messages.error(request, mensagem_erro_cpf)
        else:
            dados = dict(nome=nome, cpf=cpf, cartao_sus=cartao_sus, data_nascimento=data_nasc, sexo=sexo, telefone=telefone, endereco=endereco, numero=numero, usf_id=usf_id, micro_area_id=microarea_id, ativo=ativo, obito=obito, data_obito=data_obito)
            if paciente:
                for campo, valor in dados.items(): setattr(paciente, campo, valor)
                paciente.save()
            else:
                dados['cadastrado_por'] = request.user
                paciente = Paciente.objects.create(**dados)

            PacienteCondicao.objects.filter(paciente=paciente, data_fim__isnull=True).exclude(condicao_id__in=condicoes_ids).update(data_fim=date.today())
            for condicao_id in condicoes_ids:
                if not PacienteCondicao.objects.filter(paciente=paciente, condicao_id=int(condicao_id), data_fim__isnull=True).exists():
                    PacienteCondicao.objects.create(paciente=paciente, condicao_id=int(condicao_id), data_inicio=date.today())

            # O IF foi removido daqui! O Historico já é nativo do Core.
            hf_ids = request.POST.getlist('hf_id'); hf_condicoes = request.POST.getlist('hf_condicao')
            hf_graus = request.POST.getlist('hf_grau'); hf_obs = request.POST.getlist('hf_observacao')
            ids_mantidos = set()
            for hf_id, condicao, grau, obs in zip(hf_ids, hf_condicoes, hf_graus, hf_obs):
                condicao = condicao.strip()
                if not condicao: continue 
                if hf_id:
                    try:
                        hf = HistoricoFamiliar.objects.get(pk=hf_id, paciente=paciente)
                        hf.condicao = condicao; hf.grau_parentesco = grau; hf.observacao = obs; hf.save()
                        ids_mantidos.add(hf.pk)
                    except HistoricoFamiliar.DoesNotExist: pass
                else:
                    hf = HistoricoFamiliar.objects.create(paciente=paciente, condicao=condicao, grau_parentesco=grau, observacao=obs, registrado_por=request.user)
                    ids_mantidos.add(hf.pk)
            HistoricoFamiliar.objects.filter(paciente=paciente).exclude(pk__in=ids_mantidos).delete()

            if data_prevista_parto:
                try:
                    pc = PacienteCondicao.objects.filter(paciente=paciente, condicao__codigo='gestante', data_fim__isnull=True).first()
                    if pc: pc.data_referencia = data_prevista_parto; pc.save()
                except Exception: pass

            messages.success(request, f'Paciente "{nome}" {"atualizado" if pk else "cadastrado"}!')
            next_url = request.POST.get('next')
            if next_url: return redirect(next_url)
            return redirect('core:admin_pacientes')

    usfs = USF.objects.filter(ativo=True)
    microareas = MicroArea.objects.filter(ativo=True).select_related('usf')
    condicoes = CondicaoSaude.objects.filter(ativo=True)
    condicoes_ativas_ids = set()
    gestante_ativa = None
    if paciente:
        ativas = PacienteCondicao.objects.filter(paciente=paciente, data_fim__isnull=True).select_related('condicao')
        condicoes_ativas_ids = {pc.condicao_id for pc in ativas}
        gestante_ativa = ativas.filter(condicao__codigo='gestante').first()

    graus_parentesco = HistoricoFamiliar.GRAUS
    return render(request, 'core/pacientes/form.html', {'paciente': paciente, 'usfs': usfs, 'microareas': microareas, 'condicoes': condicoes, 'condicoes_ativas_ids': condicoes_ativas_ids, 'gestante_ativa': gestante_ativa, 'graus_parentesco': graus_parentesco, 'titulo': 'Editar paciente' if paciente else 'Novo paciente', 'acao': 'Salvar alterações' if paciente else 'Cadastrar paciente'})

@admin_required
def admin_pacientes_inativar(request):
    if request.method != 'POST': return redirect('core:admin_pacientes')
    ids = request.POST.getlist('pacientes_ids')
    if not ids: messages.error(request, 'Nenhum paciente selecionado.'); return redirect('core:admin_pacientes')

    pacientes_impacto = []
    total_na_fila = 0
    Encaminhamento = apps.get_model('encaminhamentos', 'Encaminhamento') if apps.is_installed('encaminhamentos') else None

    for pid in ids:
        try: p = Paciente.objects.get(pk=pid)
        except Paciente.DoesNotExist: continue
        na_fila = 0; disponiveis = 0; concluidos = 0; enc_fila = []
        if Encaminhamento:
            enc_fila = Encaminhamento.objects.filter(paciente=p, status__in=['aguardando', 'regulacao', 'upae']).select_related('tipo')
            na_fila = enc_fila.count()
            disponiveis = Encaminhamento.objects.filter(paciente=p, status='disponivel').count()
            concluidos = Encaminhamento.objects.filter(paciente=p, status__in=['entregue', 'cancelado', 'unificada']).count()
        total_na_fila += na_fila
        pacientes_impacto.append({'paciente': p, 'na_fila': na_fila, 'enc_fila': enc_fila, 'disponiveis': disponiveis, 'concluidos': concluidos})

    return render(request, 'core/pacientes/inativar.html', {'pacientes': pacientes_impacto, 'total_na_fila': total_na_fila, 'q': request.POST.get('q', ''), 'microarea_filtro': request.POST.get('microarea', ''), 'situacao_filtro': request.POST.get('situacao', '')})

@admin_required
def admin_pacientes_inativar_confirmar(request):
    if request.method != 'POST': return redirect('core:admin_pacientes')
    ids = request.POST.getlist('pacientes_ids')
    if not ids: messages.error(request, 'Nenhum paciente selecionado.'); return redirect('core:admin_pacientes')
    total = Paciente.objects.filter(pk__in=ids, obito=False).update(ativo=False)
    q = request.POST.get('q', ''); microarea_filtro = request.POST.get('microarea', ''); situacao_filtro = request.POST.get('situacao', '')
    messages.success(request, f'✅ {total} paciente{"s" if total != 1 else ""} inativado{"s" if total != 1 else ""} com sucesso.')
    return redirect(reverse('core:admin_pacientes') + f'?q={q}&microarea={microarea_filtro}&situacao={situacao_filtro}')


@admin_required
def importar_pacientes(request):
    usf = USF.objects.filter(ativo=True).first()
    if request.method == 'POST' and request.FILES.get('arquivo'):
        arquivo = request.FILES['arquivo']
        try: conteudo = arquivo.read().decode('latin-1')
        except Exception: messages.error(request, 'Erro ao ler o ficheiro.'); return redirect('core:importar_pacientes')
        linhas = conteudo.splitlines()
        linha_header = next((i for i, linha in enumerate(linhas) if 'Nome equipe' in linha or 'Nome' in linha and 'equipe' in linha), None)
        if linha_header is None: messages.error(request, 'Formato inválido. Cabeçalho não encontrado.'); return redirect('core:importar_pacientes')
        
        Paciente.objects.filter(usf=usf).update(atualizado=False)
        reader = csv.DictReader(linhas[linha_header:], delimiter=';')
        criados = 0; atualizados = 0; ignorados = 0; erros = []

        for linha in reader:
            nome = linha.get('Nome', '').strip()
            if not nome: continue
            cpf_cns = linha.get('CPF/CNS', '').strip()
            cpf = None; cartao_sus = None
            if cpf_cns and cpf_cns not in ['-', '']:
                cpf_limpo = ''.join(c for c in cpf_cns if c.isdigit())
                if len(cpf_limpo) == 11: cpf = cpf_limpo
                elif len(cpf_limpo) == 15: cartao_sus = cpf_limpo
                else: ignorados += 1; erros.append(f'{nome} — CPF/CNS inválido.'); continue
            if not cpf and not cartao_sus: ignorados += 1; erros.append(f'{nome} — sem CPF ou CNS válido.'); continue
            
            microarea_cod = linha.get('Microárea', '').strip()
            microarea = None
            if microarea_cod and microarea_cod not in ['-', 'Não informada', '']:
                microarea = MicroArea.objects.filter(codigo=microarea_cod, usf=usf).first() or MicroArea.objects.filter(codigo__icontains=microarea_cod, usf=usf).first()

            sexo = 'M' if 'Masculino' in linha.get('Sexo', '') else 'F' if 'Feminino' in linha.get('Sexo', '') else 'I'
            data_nasc = None
            if linha.get('Data de nascimento', '') not in ['-', '']:
                try: data_nasc = datetime.strptime(linha.get('Data de nascimento', '').strip(), '%d/%m/%Y').date()
                except ValueError: pass

            tel_raw = linha.get('Telefone celular', '').strip()
            telefone = ''.join(c for c in tel_raw if c.isdigit()) if tel_raw != '-' else ''
            
            endereco = ''; numero = ''
            endereco_raw = linha.get('Endereço', '').strip()
            if endereco_raw and endereco_raw != '-':
                rua_num = endereco_raw.split('.')[0].strip()
                if ',' in rua_num: idx = rua_num.rfind(','); endereco = rua_num[:idx].strip(); numero = rua_num[idx+1:].strip()
                else: endereco = rua_num

            try:
                paciente = Paciente.objects.filter(usf=usf, cpf=cpf).first() if cpf else Paciente.objects.filter(usf=usf, cartao_sus=cartao_sus).first() if cartao_sus else None
                dados = dict(nome=nome, sexo=sexo, data_nascimento=data_nasc, telefone=telefone, endereco=endereco, numero=numero, micro_area=microarea, usf=usf, atualizado=True, ultima_atualizacao=timezone.now())
                if cpf: dados['cpf'] = cpf
                if cartao_sus: dados['cartao_sus'] = cartao_sus
                if paciente:
                    for campo, valor in dados.items(): setattr(paciente, campo, valor)
                    paciente.save(); atualizados += 1
                else:
                    dados['cadastrado_por'] = request.user
                    Paciente.objects.create(**dados); criados += 1
            except Exception as e: erros.append(f'{nome} — erro: {str(e)}'); ignorados += 1

        vivos_fora_area = Paciente.objects.filter(usf=usf, atualizado=False, obito=False)
        total_fora = vivos_fora_area.count(); vivos_fora_area.update(micro_area=None, ativo=False)
        obitos_mantidos = Paciente.objects.filter(usf=usf, atualizado=False, obito=True)
        total_obitos_mantidos = obitos_mantidos.count(); obitos_mantidos.update(ativo=False)

        messages.success(request, f'Importação concluída! {criados} criados · {atualizados} atualizados · {ignorados} ignorados. 📦 {total_fora} vivos movidos para fora de área e ⚰️ {total_obitos_mantidos} óbitos mantidos no território.')
        return redirect('core:importar_pacientes')
    return render(request, 'core/admin/importar_pacientes.html', {'usf': usf, 'total_pacientes': Paciente.objects.filter(usf=usf).count() if usf else 0})

@admin_required
def importar_condicoes(request):
    messages.warning(request, 'A importação detalhada de condições será reativada no Módulo Clínico.')
    return redirect('core:painel_admin')

@admin_required
def importar_territorio(request):
    messages.warning(request, 'A importação de território requer o módulo de Territorialização.')
    return redirect('core:painel_admin')

@admin_required
def familias_score(request):
    messages.warning(request, 'O score familiar requer o módulo de Territorialização.')
    return redirect('core:painel_admin')

@admin_required
def familia_detalhe(request, cpf_responsavel):
    messages.warning(request, 'O detalhe familiar requer o módulo de Territorialização.')
    return redirect('core:painel_admin')

@admin_required
def admin_sentinelas(request):
    messages.warning(request, 'As sentinelas requerem o módulo de Territorialização.')
    return redirect('core:painel_admin')

@admin_required
def admin_sentinela_salvar(request, pk=None):
    messages.warning(request, 'As sentinelas requerem o módulo de Territorialização.')
    return redirect('core:painel_admin')

@admin_required
def admin_condicoes(request):
    return render(request, 'core/admin/condicoes.html', {'condicoes': CondicaoSaude.objects.order_by('nome')})

@admin_required
def admin_condicao_salvar(request, pk=None):
    condicao = get_object_or_404(CondicaoSaude, pk=pk) if pk else None
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip(); codigo = request.POST.get('codigo', '').strip(); icone = request.POST.get('icone', '').strip()
        afeta_prioridade = request.POST.get('afeta_prioridade') == 'on'; ativo = request.POST.get('ativo') == 'on'
        if not nome or not codigo: messages.error(request, 'Nome e código são obrigatórios.')
        else:
            dados = dict(nome=nome, codigo=codigo, icone=icone, afeta_prioridade=afeta_prioridade, ativo=ativo)
            if condicao:
                for campo, valor in dados.items(): setattr(condicao, campo, valor)
                condicao.save(); messages.success(request, f'Condição "{nome}" atualizada!')
            else: CondicaoSaude.objects.create(**dados); messages.success(request, f'Condição "{nome}" criada!')
            return redirect('core:admin_condicoes')
    return render(request, 'core/admin/condicao_form.html', {'condicao': condicao, 'titulo': 'Editar condição' if condicao else 'Nova condição', 'acao': 'Salvar' if condicao else 'Criar'})

@user_passes_test(lambda u: u.is_superuser)
def executar_git_pull(request):
    try:
        caminho_projeto = settings.BASE_DIR
        subprocess.run(['git', 'pull', 'origin', 'main'], cwd=caminho_projeto, capture_output=True, text=True, check=True)
        subprocess.run(['python', 'manage.py', 'migrate'], cwd=caminho_projeto, check=True)
        subprocess.run(['python', 'manage.py', 'collectstatic', '--noinput'], cwd=caminho_projeto, check=True)
        messages.success(request, '🚀 Sincronização concluída com sucesso.')
    except Exception as e: messages.error(request, f'❌ Erro inesperado: {str(e)}')
    return redirect('core:painel_admin')