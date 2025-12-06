import csv
import re
import os
import sys

# ==========================================
# 1. ESTRUTURAS DE DADOS
# ==========================================
class Automato:
    def __init__(self, nome="Autômato"):
        self.nome = nome
        self.estados = set()
        self.alfabeto = set()
        self.inicial = None
        self.finais = set()
        # Estrutura: { 'Origem': {'a': {'Destino1', 'Destino2'}} }
        self.transicoes = {}

    def criar_transicao(self, origem, simbolo, destino):
        self.estados.add(origem)
        self.estados.add(destino)
        self.alfabeto.add(simbolo)
        
        if origem not in self.transicoes:
            self.transicoes[origem] = {}
        
        if simbolo not in self.transicoes[origem]:
            self.transicoes[origem][simbolo] = set()
        
        self.transicoes[origem][simbolo].add(destino)

    def set_inicial(self, estado):
        self.inicial = estado
        self.estados.add(estado)

    def add_final(self, estado):
        self.finais.add(estado)
        self.estados.add(estado)

    def __repr__(self):
        return f"[{self.nome}] {len(self.estados)} estados. Inicial: {self.inicial}"

# Função auxiliar para nomear estados compostos (ex: {A, B} vira "AB")
def nome_estado(conjunto):
    if not conjunto: return "DEAD" 
    
    # Filtra valores None para evitar erros e converte tudo para string
    lista_limpa = [str(x) for x in conjunto if x is not None]
    
    if not lista_limpa: return "ERRO"
    
    lista = sorted(lista_limpa)
    return "".join(lista)

# ==========================================
# 2. ALGORITMOS PRINCIPAIS
# ==========================================

# --- ETAPA 1: Leitura da Gramática -> AFND ---
def gramatica_para_afnd(caminho_arquivo):
    afnd = Automato("AFND Gerado da Gramática")
    estado_Z = "Z_FIM" # Estado final auxiliar
    
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            # Lê linhas ignorando as vazias
            linhas = [l.strip() for l in f.readlines() if l.strip()]
    except FileNotFoundError:
        # Retornamos None para tratar o erro na main
        return None

    for linha in linhas:
        if '::=' not in linha: continue

        esquerda, direita = linha.split('::=')
        origem = esquerda.strip().replace('<', '').replace('>', '')
        
        # O primeiro não-terminal lido é definido como inicial
        if afnd.inicial is None:
            afnd.set_inicial(origem)

        producoes = [p.strip() for p in direita.split('|')]

        for prod in producoes:
            # Caso Epsilon
            if prod == 'ε' or prod == '':
                afnd.add_final(origem)
                continue

            # Regex para separar terminal e não terminal (ex: a<A> ou apenas a)
            match = re.match(r'([^<]+)(?:<(.+)>)?', prod)
            
            if match:
                simbolo = match.group(1).strip()
                destino_temp = match.group(2)
                
                if destino_temp:
                    destino = destino_temp.strip()
                    afnd.criar_transicao(origem, simbolo, destino)
                else:
                    # Vai para estado final Z se for terminal puro
                    afnd.criar_transicao(origem, simbolo, estado_Z)
                    afnd.add_final(estado_Z)
    
    if afnd.inicial is None:
        print("ERRO: Gramática vazia ou inválida (nenhuma regra '::=' encontrada).")
        return None
        
    return afnd

# --- ETAPA 2: AFND -> AFD ---
def afnd_para_afd(afnd):
    afd = Automato("AFD Convertido")
    afd.alfabeto = afnd.alfabeto

    # Estado inicial é o conjunto {Inicial do AFND}
    inicial_set = frozenset([afnd.inicial])
    nome_inicial = nome_estado(inicial_set)
    
    afd.set_inicial(nome_inicial)
    
    # Se o inicial do AFND era final, o do AFD também é
    if afnd.inicial in afnd.finais: 
        afd.add_final(nome_inicial)

    fila = [inicial_set]
    processados = set()
    mapa_conjuntos = {inicial_set: nome_inicial}

    while fila:
        atual_set = fila.pop(0)
        nome_atual = mapa_conjuntos[atual_set]

        if nome_atual in processados: continue
        processados.add(nome_atual)

        # Para cada símbolo, descobrir a união dos destinos
        for simbolo in sorted(list(afnd.alfabeto)):
            proximo_set = set()
            
            for sub_estado in atual_set:
                if sub_estado in afnd.transicoes and simbolo in afnd.transicoes[sub_estado]:
                    destinos = afnd.transicoes[sub_estado][simbolo]
                    proximo_set.update(destinos)
            
            if not proximo_set: continue

            proximo_set_f = frozenset(proximo_set)
            nome_proximo = nome_estado(proximo_set_f)

            if proximo_set_f not in mapa_conjuntos:
                mapa_conjuntos[proximo_set_f] = nome_proximo
                fila.append(proximo_set_f)
                
                # Verifica se é final (se contiver algum final do AFND)
                eh_final = any(e in afnd.finais for e in proximo_set_f)
                if eh_final:
                    afd.add_final(nome_proximo)

            afd.criar_transicao(nome_atual, simbolo, nome_proximo)

    return afd

# --- ETAPA 3: Minimização (Particionamento) ---
def minimizar_afd(afd):
    # 1. Separa Finais e Não-Finais
    finais = frozenset(afd.finais)
    nao_finais = frozenset(afd.estados - afd.finais)
    particoes = {finais, nao_finais}
    particoes = {p for p in particoes if p} # Remove vazios

    while True:
        novas_particoes = set()
        
        for grupo in particoes:
            if len(grupo) <= 1:
                novas_particoes.add(grupo)
                continue

            sub_grupos = {}
            
            for estado in grupo:
                # Assinatura: Para qual grupo vou com cada símbolo?
                assinatura = []
                for simb in sorted(list(afd.alfabeto)):
                    dest = None
                    if estado in afd.transicoes and simb in afd.transicoes[estado]:
                        dest_nome = list(afd.transicoes[estado][simb])[0]
                        # Descobre ID da partição do destino
                        for i, part in enumerate(particoes):
                            if dest_nome in part:
                                dest = i
                                break
                    assinatura.append(dest)
                
                assinatura = tuple(assinatura)
                if assinatura not in sub_grupos: sub_grupos[assinatura] = set()
                sub_grupos[assinatura].add(estado)
            
            for sub in sub_grupos.values():
                novas_particoes.add(frozenset(sub))

        if novas_particoes == particoes:
            break
        particoes = novas_particoes

    # Reconstrução
    afd_min = Automato("AFD Mínimo")
    afd_min.alfabeto = afd.alfabeto
    
    mapa_novo = {}
    for grupo in particoes:
        nome_grupo = "".join(sorted(list(grupo)))
        
        if afd.inicial in grupo:
            afd_min.set_inicial(nome_grupo)
        
        if not grupo.isdisjoint(afd.finais):
            afd_min.add_final(nome_grupo)
            
        for estado in grupo:
            mapa_novo[estado] = nome_grupo

    for grupo in particoes:
        rep = list(grupo)[0]
        origem_nova = mapa_novo[rep]
        
        if rep in afd.transicoes:
            for simb, dests in afd.transicoes[rep].items():
                dest_antigo = list(dests)[0]
                if dest_antigo in mapa_novo:
                    dest_novo = mapa_novo[dest_antigo]
                    afd_min.criar_transicao(origem_nova, simb, dest_novo)

    return afd_min

# --- ETAPA 4: Salvar CSV ---
def salvar_csv(automato, nome_arquivo):
    try:
        with open(nome_arquivo, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Estado', 'Simbolo', 'Destino', 'Eh_Inicial', 'Eh_Final'])
            
            for estado in sorted(list(automato.estados)):
                eh_ini = "SIM" if estado == automato.inicial else ""
                eh_fim = "SIM" if estado in automato.finais else ""
                
                if estado in automato.transicoes:
                    for simb, dests in automato.transicoes[estado].items():
                        destino_str = " | ".join(sorted(list(dests)))
                        writer.writerow([estado, simb, destino_str, eh_ini, eh_fim])
                elif eh_fim == "SIM":
                     writer.writerow([estado, "-", "-", eh_ini, eh_fim])
        print(f"\n[SUCESSO] Relatório salvo em: {nome_arquivo}")
    except Exception as e:
        print(f"Erro ao salvar arquivo CSV: {e}")

# ==========================================
# 3. EXECUÇÃO DINÂMICA
# ==========================================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("   CONVERSOR DE GRAMÁTICA -> AFD MÍNIMO")
    print("="*50)
    print("Certifique-se que o arquivo de texto com a gramática")
    print("está na mesma pasta deste script.")
    print("-" * 50)
    
    # 1. Pede o nome do arquivo ao usuário
    nome_entrada = input("Digite o nome do arquivo de entrada (ex: gramatica.txt): ").strip()

    # 2. Verifica se o arquivo existe antes de tentar qualquer coisa
    if not os.path.exists(nome_entrada):
        print(f"\n[ERRO CRÍTICO] O arquivo '{nome_entrada}' não foi encontrado.")
        print("Verifique o nome e tente novamente.")
    else:
        # 3. Executa a pipeline com o arquivo escolhido
        print(f"\n--- LENDO ARQUIVO: {nome_entrada} ---")
        
        try:
            # Passo A: Ler Gramática e criar AFND
            afnd = gramatica_para_afnd(nome_entrada)
            
            if afnd:
                print(f"[OK] Gramática lida. AFND gerado com {len(afnd.estados)} estados.")
                
                # Passo B: Converter para AFD
                afd = afnd_para_afd(afnd)
                print(f"[OK] Convertido para AFD ({len(afd.estados)} estados).")
                
                # Passo C: Minimizar
                afd_min = minimizar_afd(afd)
                print(f"[OK] AFD Minimizado ({len(afd_min.estados)} estados).")
                
                # Passo D: Salvar Saída
                nome_saida = f"saida_{os.path.splitext(nome_entrada)[0]}.csv"
                salvar_csv(afd_min, nome_saida)
            
        except Exception as e:
            print(f"\n[ERRO DE EXECUÇÃO]: {e}")
