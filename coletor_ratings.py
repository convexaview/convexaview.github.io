"""
Coletor de Ratings Bancários — Convexa News
Puxa ratings de crédito das páginas oficiais de RI dos bancos.
Gera: ratings.json (consumido pelo coletor_raiox.py)

Fontes: Páginas de Relações com Investidores de cada banco
Frequência: 1x por mês (ratings mudam raramente)
"""

import json
import sys
import io
import re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from datetime import datetime

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# ==================== FONTES DE RATINGS POR BANCO ====================
# Cada banco tem uma URL de RI e uma função de parsing específica
BANCOS_RI = [
    {
        'nome': 'Banco do Brasil',
        'url': 'https://ri.bb.com.br/en/banco-do-brasil/ratings/',
        'parser': 'parse_bb',
    },
    {
        'nome': 'Banrisul',
        'url': 'https://ri.banrisul.com.br/en/market-information/ratings/',
        'parser': 'parse_banrisul',
    },
    {
        'nome': 'Nubank',
        'url': 'https://www.investidores.nu/ratings/',
        'parser': 'parse_nubank',
    },
    {
        'nome': 'Inter',
        'url': 'https://investors.inter.co/en/investor-updates/ratings/',
        'parser': 'parse_inter',
    },
]


def fetch_page(url):
    """Baixa uma página HTML."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = 'utf-8'
        if resp.status_code == 200:
            return resp.text
        print(f"    HTTP {resp.status_code}")
        return None
    except Exception as e:
        print(f"    Erro: {e}")
        return None


def clean_text(html_text):
    """Remove tags HTML e limpa texto."""
    return re.sub(r'<[^>]+>', '', html_text).strip()


def find_rating_value(html, agency_pattern, rating_pattern=r'[A-D][a-z]*[\d]*[\+\-]?(?:\.[a-z]+)?'):
    """Busca um rating próximo a um padrão de agência no HTML."""
    # Procura o nome da agência e pega o rating mais próximo
    matches = re.finditer(agency_pattern, html, re.IGNORECASE)
    for m in matches:
        # Pega os próximos 500 chars após o match
        after = html[m.end():m.end()+500]
        # Procura padrões de rating
        rating_match = re.search(r'((?:Baa|Ba|B|Aaa|Aa|A|Caa|Ca|C)[123]?|(?:AAA|AA|A|BBB|BB|B|CCC|CC|C)[\+\-]?)', after)
        if rating_match:
            return rating_match.group(1)
    return ''


# ==================== PARSERS ESPECÍFICOS ====================

def parse_bb(html):
    """Parser para Banco do Brasil RI."""
    ratings = {'moodys': '', 'fitch': '', 'sp': '', 'perspectiva': ''}

    # Moody's - procurar "Moody" seguido de rating Ba1/Ba2/etc
    m = re.search(r"Moody.{0,100}?(Ba[123]|Baa[123]|B[123])", html, re.IGNORECASE | re.DOTALL)
    if m:
        ratings['moodys'] = m.group(1)

    # Fitch - procurar "Fitch" seguido de BB/BB+/etc
    f = re.search(r"Fitch.{0,200}?(?:Long.{0,50}?Term|IDR).{0,100}?(BBB[\+\-]?|BB[\+\-]?|B[\+\-]?)", html, re.IGNORECASE | re.DOTALL)
    if f:
        ratings['fitch'] = f.group(1)

    # S&P
    s = re.search(r"(?:Standard|S&amp;P|S&P).{0,200}?(?:Long.{0,50}?Term).{0,100}?(BBB[\+\-]?|BB[\+\-]?|B[\+\-]?)", html, re.IGNORECASE | re.DOTALL)
    if s:
        ratings['sp'] = s.group(1)

    # Perspectiva
    persp = re.search(r'(Stable|Positive|Negative|Est[áa]vel|Positiv[ao]|Negativ[ao])', html, re.IGNORECASE)
    if persp:
        p = persp.group(1).lower()
        ratings['perspectiva'] = 'Estável' if 'stab' in p or 'est' in p else 'Positiva' if 'posit' in p else 'Negativa'

    return ratings


def parse_banrisul(html):
    """Parser para Banrisul RI."""
    ratings = {'moodys': '', 'fitch': '', 'sp': '', 'perspectiva': ''}

    # Fitch IDR
    f = re.search(r"Fitch.{0,400}?(?:Foreign|Long).{0,100}?(?:Long.{0,30}?Term|IDR).{0,80}?(BB[\+\-]?|B[\+\-]?|BBB[\+\-]?)", html, re.IGNORECASE | re.DOTALL)
    if f:
        ratings['fitch'] = f.group(1)

    # Moody's Deposits
    m = re.search(r"Moody.{0,200}?(?:Deposit|Long).{0,80}?(Ba[123]|Baa[123]|B[123])", html, re.IGNORECASE | re.DOTALL)
    if m:
        ratings['moodys'] = m.group(1)

    # S&P
    s = re.search(r"(?:Standard|S&amp;P|S&P).{0,200}?(?:Issuer|Credit|Global).{0,80}?(BB[\+\-]?|B[\+\-]?|BBB[\+\-]?)", html, re.IGNORECASE | re.DOTALL)
    if s:
        ratings['sp'] = s.group(1)

    # Perspectiva
    persp_m = re.search(r"Moody.{0,200}?(Stable|Positive|Negative)", html, re.IGNORECASE | re.DOTALL)
    persp_f = re.search(r"Fitch.{0,200}?(Stable|Positive|Negative)", html, re.IGNORECASE | re.DOTALL)
    if persp_m:
        p = persp_m.group(1).lower()
        ratings['perspectiva'] = 'Estável' if 'stab' in p else 'Positiva' if 'posit' in p else 'Negativa'
    elif persp_f:
        p = persp_f.group(1).lower()
        ratings['perspectiva'] = 'Estável' if 'stab' in p else 'Positiva' if 'posit' in p else 'Negativa'

    return ratings


def parse_nubank(html):
    """Parser para Nubank RI."""
    ratings = {'moodys': '', 'fitch': '', 'sp': '', 'perspectiva': ''}

    # Moody's Global - Nu Financeira (mais relevante)
    m = re.search(r"Moody.{0,50}?Global.{0,200}?Nu Financ.{0,100}?(Ba[123]|Baa[123])", html, re.IGNORECASE | re.DOTALL)
    if not m:
        m = re.search(r"Moody.{0,300}?(Ba[123]|Baa[123]).{0,20}?(?:/|Stable|Positive)", html, re.IGNORECASE | re.DOTALL)
    if m:
        ratings['moodys'] = m.group(1)

    # S&P Global - Nu Financeira
    s = re.search(r"S&amp;P.{0,50}?Global.{0,200}?Nu Financ.{0,100}?(BB[\+\-]?|BBB[\+\-]?)", html, re.IGNORECASE | re.DOTALL)
    if not s:
        s = re.search(r"S.P.{0,50}?Global.{0,200}?(BB[\+\-]?|BBB[\+\-]?)", html, re.IGNORECASE | re.DOTALL)
    if s:
        ratings['sp'] = s.group(1)

    # Perspectiva
    persp = re.search(r'(Stable|Positive|Negative|Est[áa]vel|Positiv[ao])', html, re.IGNORECASE)
    if persp:
        p = persp.group(1).lower()
        ratings['perspectiva'] = 'Estável' if 'stab' in p or 'est' in p else 'Positiva' if 'posit' in p else 'Negativa'

    return ratings


def parse_inter(html):
    """Parser para Banco Inter RI."""
    ratings = {'moodys': '', 'fitch': '', 'sp': '', 'perspectiva': ''}

    # Moody's
    m = re.search(r"Moody.{0,200}?(AA[\+\-]?|A[\+\-]?|Ba[123]|Baa[123])", html, re.IGNORECASE | re.DOTALL)
    if m:
        val = m.group(1)
        if 'AA' in val:
            ratings['moodys'] = val + '.br'  # escala nacional
        else:
            ratings['moodys'] = val

    # S&P
    s = re.search(r"(?:Standard|S&amp;P|S&P).{0,200}?(AA[\+\-]?|A[\+\-]?|BB[\+\-]?)", html, re.IGNORECASE | re.DOTALL)
    if s:
        val = s.group(1)
        ratings['sp'] = val + ' Nacional' if 'AA' in val else val

    # Perspectiva
    persp = re.search(r'(Stable|Positive|Negative|Est[áa]vel|Positiv[ao])', html, re.IGNORECASE)
    if persp:
        p = persp.group(1).lower()
        ratings['perspectiva'] = 'Estável' if 'stab' in p or 'est' in p else 'Positiva' if 'posit' in p else 'Negativa'

    return ratings


# Mapeamento de funções
PARSERS = {
    'parse_bb': parse_bb,
    'parse_banrisul': parse_banrisul,
    'parse_nubank': parse_nubank,
    'parse_inter': parse_inter,
}

# ==================== RATINGS VIA MOODY'S PRESS RELEASE ====================
# Para bancos sem página de RI acessível, usar dados do upgrade em massa de Out/2025
# Fonte: Investidor10, XP Conteúdos (reportagem sobre ação da Moody's)
RATINGS_MOODYS_OUT2025 = {
    'Itaú Unibanco': 'Ba1',
    'Bradesco': 'Ba1',
    'Santander Brasil': 'Ba1',
    'Caixa Econômica': 'Ba1',
    'BTG Pactual': 'Ba1',
    'Safra': 'Ba1',
    'Sicredi': 'Ba1',
    'ABC Brasil': 'Ba1',
    'Daycoval': 'Ba1',
    'Banco do Nordeste': 'Ba1',
    'Banco da Amazônia': 'Ba1',
    'Votorantim': 'Ba1',
}

# Fitch ratings confirmados por press releases
RATINGS_FITCH_CONFIRMADOS = {
    'Itaú Unibanco': {'rating': 'BB+', 'data': 'Dez/2025'},
    'Bradesco': {'rating': 'BB+', 'data': 'Dez/2025'},
    'BTG Pactual': {'rating': 'BB+', 'data': 'Mar/2026', 'perspectiva': 'Positiva'},
    'BMG': {'rating': 'B+', 'data': 'Fitch'},
}


def main():
    if not HAS_REQUESTS:
        return

    print("=" * 60)
    print("  COLETOR DE RATINGS BANCÁRIOS")
    print("  Fontes: Páginas oficiais de RI + Press Releases")
    print("=" * 60)

    all_ratings = {}

    # 1. Buscar nas páginas de RI
    print("\n  [1/3] Buscando nas páginas de RI dos bancos...\n")
    for banco_info in BANCOS_RI:
        nome = banco_info['nome']
        url = banco_info['url']
        parser_name = banco_info['parser']
        parser_func = PARSERS.get(parser_name)

        print(f"  {nome}...", end=' ', flush=True)
        html = fetch_page(url)
        if html and parser_func:
            ratings = parser_func(html)
            if any(ratings.get(k) for k in ['moodys', 'fitch', 'sp']):
                ratings['fonte'] = f"RI oficial ({url.split('/')[2]})"
                all_ratings[nome] = ratings
                print(f"Moody's={ratings['moodys'] or '—'} Fitch={ratings['fitch'] or '—'} S&P={ratings['sp'] or '—'} [{ratings['perspectiva']}]")
            else:
                print("Sem ratings encontrados")
        else:
            print("Página indisponível")

    # 2. Complementar com Moody's upgrade Oct/2025
    print("\n  [2/3] Complementando com Moody's (upgrade Out/2025)...\n")
    for nome, rating in RATINGS_MOODYS_OUT2025.items():
        if nome not in all_ratings:
            all_ratings[nome] = {'moodys': rating, 'fitch': '', 'sp': '', 'perspectiva': 'Estável', 'fonte': "Moody's (Out/2025)"}
            print(f"  {nome}: Moody's {rating}")
        elif not all_ratings[nome].get('moodys'):
            all_ratings[nome]['moodys'] = rating
            print(f"  {nome}: +Moody's {rating}")

    # 3. Complementar com Fitch confirmados
    print("\n  [3/3] Complementando com Fitch (press releases)...\n")
    for nome, fdata in RATINGS_FITCH_CONFIRMADOS.items():
        if nome not in all_ratings:
            all_ratings[nome] = {'moodys': '', 'fitch': fdata['rating'], 'sp': '', 'perspectiva': fdata.get('perspectiva', 'Estável'), 'fonte': f"Fitch ({fdata['data']})"}
            print(f"  {nome}: Fitch {fdata['rating']}")
        elif not all_ratings[nome].get('fitch'):
            all_ratings[nome]['fitch'] = fdata['rating']
            if fdata.get('perspectiva'):
                all_ratings[nome]['perspectiva'] = fdata['perspectiva']
            print(f"  {nome}: +Fitch {fdata['rating']}")

    # Salvar
    output = {
        'atualizado_em': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'total': len(all_ratings),
        'ratings': all_ratings,
    }

    with open('ratings.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n  ratings.json salvo — {len(all_ratings)} bancos com ratings")
    print("  Concluído!")


if __name__ == '__main__':
    main()
