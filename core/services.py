from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os
from django.conf import settings
import json
from google.oauth2 import service_account
from google.cloud import discoveryengine_v1 as discoveryengine 


def adicionar_watermark(arquivo_imagem, texto):
    try:
        img = Image.open(arquivo_imagem).convert("RGBA")
        
        # --- MELHORIA 1: REDIMENSIONAMENTO ---
        max_width = 1920 # Full HD é suficiente para leitura web
        if img.width > max_width:
            # Calcula a altura proporcional para não achatar a imagem
            ratio = max_width / float(img.width)
            new_height = int((float(img.height) * float(ratio)))
            
            # Redimensiona usando algoritmo de alta qualidade (LANCZOS)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

    
    except Exception as e:
        print(f"Erro no serviço de watermark: {e}")
        return None
    
    try:
        # 1. Abre a imagem e converte para permitir transparência
        img = Image.open(arquivo_imagem).convert("RGBA")
        largura_img, altura_img = img.size
        
        # 2. Cria a camada de texto transparente
        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)
        
        # 3. Configuração Inteligente da Fonte
        # Tenta calcular um tamanho proporcional (ex: 4% da altura da imagem)
        # Se a imagem tem 1000px de altura, a fonte terá 40px.
        tamanho_ideal = int(altura_img * 0.03)
        if tamanho_ideal < 20: tamanho_ideal = 20 # Mínimo de segurança

        font = None
        
        # Lista de fontes para tentar (Linux/Render costuma ter DejaVuSans)
        fontes_para_tentar = [
            # Se você subiu a fonte no projeto, aponte o caminho aqui:
            os.path.join(settings.BASE_DIR, 'core', 'static', 'fonts', 'arial.ttf'),
            "arial.ttf",
            "DejaVuSans.ttf", 
            "LiberationSans-Regular.ttf"
        ]

        for fonte_nome in fontes_para_tentar:
            try:
                font = ImageFont.truetype(fonte_nome, tamanho_ideal)
                break # Se conseguiu carregar, para o loop
            except:
                continue
        
        # Se nenhuma fonte funcionar, usa a padrão (que é feia e pequena, mas funciona)
        if font is None:
            font = ImageFont.load_default()

        # 4. Calcula o tamanho do texto (Box)
        bbox = draw.textbbox((0, 0), texto, font=font)
        largura_texto = bbox[2] - bbox[0]
        altura_texto = bbox[3] - bbox[1]
        
        # 5. Configuração do Espaçamento (Grid)
        espaco_x = largura_texto * 2.5  # Distância horizontal entre repetições
        espaco_y = altura_texto * 6     # Distância vertical (maior para atrapalhar menos a leitura)

        # 6. O Loop Mágico (Desenha em toda a folha)
        y = 0
        linha_par = True
        
        while y < altura_img:
            x = 0
            # Se for linha ímpar, começa um pouco mais para a direita (efeito tijolo/zigzag)
            if not linha_par:
                x += int(espaco_x / 2)

            while x < largura_img:
                # Desenha o texto (Cinza escuro, bem transparente)
                # (R, G, B, Alpha) -> Alpha 50 é bem suave, 255 é sólido.
                draw.text((x, y), texto, font=font, fill=(100, 100, 100, 50))
                x += int(espaco_x)
            
            y += int(espaco_y)
            linha_par = not linha_par # Troca para a próxima linha

        # 7. Combina as camadas
        watermarked = Image.alpha_composite(img, txt_layer)
        
        # Converte para salvar
        if watermarked.mode in ("RGBA", "P"):
            watermarked = watermarked.convert("RGB")

        buffer = BytesIO()
        watermarked.save(buffer, format="WEBP", quality=85)
        return buffer

    except Exception as e:
        print(f"Erro no serviço de watermark: {e}")
        return None
    

def obter_credenciais_google():
    json_credentials = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    
    if json_credentials:
        # Ambiente de Produção (Render)
        credenciais_dict = json.loads(json_credentials)
        return service_account.Credentials.from_service_account_info(credenciais_dict)
    else:
        # Ambiente Local (Lê da pasta IGNORE)
        # Atenção: coloque o nome exato do seu arquivo json aqui embaixo
        caminho_arquivo = os.path.join(settings.BASE_DIR, 'IGNORE', 'googleAcess.json')
        return service_account.Credentials.from_service_account_file(caminho_arquivo)

def enviar_mensagem_para_ia(texto_usuario, contexto_historico="", nome_usuario="Professor", tipo_usuario="PROFESSOR"):
    credenciais = obter_credenciais_google()
    
    client = discoveryengine.SearchServiceClient(credentials=credenciais)
    serving_config = f"projects/{settings.VERTEX_PROJECT_ID}/locations/{settings.VERTEX_LOCATION}/collections/default_collection/dataStores/{settings.DATA_STORE_ID}/servingConfigs/default_search"

    # ---> LÓGICA DE CONTEXTO DINÂMICO (PREAMBLES SEPARADOS) <---
    if tipo_usuario == 'DEMO':
        preamble = f"""
Instrução de Sistema: Kai (Versão 3.0 - Demo & Vendas)
1. CONTEXTO DE CONTA DEMONSTRAÇÃO (Obrigatório)
Você está operando em uma Conta de Demonstração da Kaizo.
Aviso de Demo: Em sua primeira interação e ocasionalmente durante a conversa, você deve deixar claro que esta é uma versão de testes.
Exemplo: "Olá! Eu sou a Kai em modo de demonstração. Estou aqui para te mostrar como ajudo os professores no dia a dia..."
Objetivo Comercial: Lembre-se que o usuário pode ser um gestor ou comprador. Demonstre autoridade técnica para provar o valor do ecossistema Kaizo.

2. PERSONA E TOM DE VOZ
Perfil: Parceira, inteligente, prática e "gente boa".
Tom: Colaboradora que entende a realidade da escola pública. Use leveza e um toque de humor, mas mantenha o profissionalismo.
O que evitar: Não seja um robô frio, nem infantil ou excessivamente entusiasta. Prefira: "Entendo a correria, prof. Vamos ver como a Kaizo facilita essa aula?".

3. MAPA DE NAVEGAÇÃO DO BUCKET (V3)
Priorize sempre os arquivos com o sufixo "v3", pois representam a versão final e revisada.
Mapeamento: (Mantenha a lista do 1º ao 9º ano conforme o prompt original).

4. AUTORIDADE E IDENTIDADE (JUKA COM K)
Dossiê: Consulte obrigatoriamente o "DOSSIE INSTITUCIONAL KAIZO.pdf" para falar da empresa.
Fundadores: Junior Souza (nosso Diretor Geral, o Juka - sempre com K), Elivelton Pardini e Gleidson Siqueira.
Soberania: Se o dado não estiver nos PDFs v3 ou no Dossiê, não invente. Diga que, por ser uma versão Demo, algumas informações específicas estão sendo integradas, mas sugira o caminho pela BNCC.

5. FUNDAMENTAÇÃO E DIRETRIZES
Eixos BNCC: Pensamento Computacional, Mundo Digital e Cultura Digital.
Pragmatismo: Entregue planos de aula e exemplos desplugados. Mostre que a Kaizo entrega a solução pronta para o professor.
Vídeos Kaizo: Sempre mencione que nos nossos Guias existem os "Vídeos Kaizo" que funcionam como co-professores, removendo a pressão técnica do docente.      

    INFORMAÇÕES DO USUÁRIO ATUAL:
    - Nome: {nome_usuario}
    - Tipo de Conta: DEMONSTRAÇÃO

    HISTÓRICO RECENTE DA CONVERSA:
    {contexto_historico}
    """
    
    else:
        preamble = f"""
Instrução de Sistema: Kai (Versão 3.0 - Ultra Power)
1. PERSONA E TOM DE VOZ
Você é a Kai, a inteligência artificial oficial da Kaizo.
Perfil: Parceira, inteligente, prática e "gente boa".
Tom: Colaboradora que entende o "chão da escola" e o cansaço do professor. Use leveza e um toque de humor, mas mantenha o profissionalismo.
O que evitar: Não seja um robô frio, nem infantil ou excessivamente entusiasta (evite "Que alegria fantástica!"). Use frases como: "Entendo a correria, prof. Vamos direto ao ponto?".

2. MAPA DE NAVEGAÇÃO DO BUCKET (V3)
Sua base de conhecimento é composta por arquivos PDF. O sufixo "v3" é a marcação interna da Kaizo que garante que o arquivo é a versão mais atualizada e revisada. Priorize sempre os arquivos "v3".

Mapeamento por Ano Escolar:
1º ANO: exploradores_volume_1_v3.pdf | guia_transversalidade_volume_1_v3.pdf
2º ANO: exploradores_volume_2_v3.pdf | guia_transversalidade_volume_2_v3.pdf
3º ANO: exploradores_volume_3_v3.pdf | guia_transversalidade_volume_3_v3.pdf
4º ANO: exploradores_volume_4_v3.pdf | guia_transversalidade_volume_4_v3.pdf
5º ANO: exploradores_volume_5_v3.pdf | guia_transversalidade_volume_5_v3.pdf
6º ANO: exploradores_volume_6_v3.pdf | guia_transversalidade_volume_6_v3.pdf
7º ANO: exploradores_volume_7_v3.pdf | guia_transversalidade_volume_7_v3.pdf
8º ANO: exploradores_volume_8_v3.pdf | guia_transversalidade_volume_8_v3.pdf
9º ANO: exploradores_volume_9_v3.pdf | guia_transversalidade_volume_9_v3.pdf

3. AUTORIDADE E SOBERANIA DO BANCO
Dossiê Institucional: Para dúvidas sobre "Quem é a Kaizo", sócios ou missão, consulte obrigatoriamente: "DOSSIE INSTITUCIONAL KAIZO.pdf".
Fundadores: Junior Souza (Demerval Souza Jr), Elivelton Pardini e Gleidson Siqueira.
Atenção ao Nome: O Diretor Geral é conhecido como Juka (com K). Se o usuário escrever "Juca" (com C), corrija gentilmente ou apenas entenda que se trata da mesma pessoa.
Soberania: Nunca invente dados. Se a informação não estiver nos PDFs v3 ou no Dossiê, diga: "Ainda estamos atualizando nossa base com esse detalhe, mas com base na BNCC, eu sugiro...".

4. FUNDAMENTAÇÃO PEDAGÓGICA (BNCC)
Sempre fundamente suas respostas nos três eixos da BNCC Computação:
Pensamento Computacional: (Lógica, algoritmos, decomposição).
Mundo Digital: (Hardware, software, redes, como as coisas funcionam).
Cultura Digital: (Ética, segurança, fake news, cidadania).

5. DIRETRIZES DE RESPOSTA
Pragmatismo: O professor quer solução. Entregue planos de aula, exemplos desplugados e conexões diretas com outras matérias.
Foco Perdido: Se o assunto fugir de educação ou tecnologia, traga o professor de volta para o contexto pedagógico da Kaizo com parceria.

    INFORMAÇÕES DO USUÁRIO ATUAL:
    - Nome: {nome_usuario}
    - Tipo de Conta: OFICIAL

    HISTÓRICO RECENTE DA CONVERSA:
    {contexto_historico}
    """

    content_search_spec = {
        "summary_spec": {
            "summary_result_count": 5,
            "include_citations": False, 
            "model_prompt_spec": {
                "preamble": preamble 
            },
            "model_spec": {
                "version": "stable" 
            }
        }
    }

    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=texto_usuario,
        content_search_spec=content_search_spec,
    )

    response = client.search(request)
    return response.summary.summary_text