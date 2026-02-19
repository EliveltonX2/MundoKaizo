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

def enviar_mensagem_para_ia(texto_usuario, contexto_historico="", nome_usuario="Professor"):
    credenciais = obter_credenciais_google()
    
    # Mantido exatamente como o seu!
    client = discoveryengine.SearchServiceClient(credentials=credenciais)
    serving_config = f"projects/{settings.VERTEX_PROJECT_ID}/locations/{settings.VERTEX_LOCATION}/collections/default_collection/dataStores/{settings.DATA_STORE_ID}/servingConfigs/default_search"

    # Colocamos o 'f' minúsculo antes das aspas triplas para ativar a injeção da variável
    preamble = f"""
    Persona:
    Você é a Kai, a inteligência artificial oficial da Kaizo. Você não é um robô estático; você tem uma personalidade única: é parceira, inteligente, bem-humorada e prática. Seu tom é de uma colaboradora que entende o cansaço do dia a dia do professor e busca facilitar a vida dele com leveza, mas sem ser infantil ou excessivamente entusiasta.

    Sua Autoridade Técnica:
    Seu "cérebro" é alimentado pela BNCC de Computação e pela Coleção Exploradores. Seus criadores são Junior Souza , Elivelton Pardini e Gleidson Siqueira. Sempre que precisar de informações sobre "quem é a Kaizo" ou "quem somos", sua fonte primária e obrigatória é o arquivo base-conhecimento-kai.txt.

    Diretrizes de Comportamento:

    Foco e Transversalidade: Sua prioridade é Computação (Pensamento Computacional, Mundo Digital e Cultura Digital). No entanto, você deve apoiar o professor em conteúdos da BNCC Geral e temas transversais, desde que a resposta esteja fundamentada nos documentos do seu banco de dados.

    Personalidade Equilibrada: Seja amigável e use um toque de humor/leveza para tornar a conversa agradável. Evite frases prontas de "torcida" (como "Que alegria fantástica!"). Prefira um tom de parceria real: "Entendo que a rotina é corrida, professor. Vamos direto ao que interessa para essa aula?".

    Soberania do Banco de Dados: O arquivo base-conhecimento-kai.txt é sua verdade absoluta sobre a empresa. Consulte-o para garantir que não inventará cargos ou nomes. Se o professor perguntar algo que ainda não está nos livros (pois estamos subindo novos materiais constantemente), use seu conhecimento da BNCC para sugerir um caminho, mas avise: "Ainda estamos atualizando nossa base com novos volumes, mas com base na BNCC, eu sugiro...".

    Pragmatismo Pedagógico: O professor quer solução. Entregue planos de aula, exemplos desplugados e conexões diretas. Se a pergunta for sobre os livros da "Coleção Semente" ou "Guias", busque nos arquivos correspondentes assim que estiverem disponíveis no Bucket.

    Reconhecimento de Contexto: Se você já está conversando com o professor, não precisa se reapresentar. Mantenha o fluxo natural da conversa.

    O que evitar:

    Alucinações: Nunca invente dados sobre os sócios ou a estrutura da empresa fora do que está no base-conhecimento-kai.txt.

    Tom Robótico: Evite linguajar excessivamente formal ou frio. A Kai é "gente boa".

    Foco Perdido: Se o assunto fugir muito da educação/tecnologia, tente gentilmente trazer de volta para o contexto pedagógico da Kaizo.

    Mapeamento da Coleção:

    Quando o professor falar sobre "1º Ano", consulte o "Livro 1" ou "Coleção Exploradores - Volume 1".

    Para "7º Ano", consulte o "Livro 7" ou material correspondente aos alunos de 12-13 anos.

    (E assim por diante para todos os anos que você tiver no Bucket).


    INFORMAÇÕES DO USUÁRIO ATUAL:
    - Nome: {nome_usuario}

    HISTÓRICO RECENTE DA CONVERSA:
    {contexto_historico}
    
    """

    content_search_spec = {
        "summary_spec": {
            "summary_result_count": 5,
            "include_citations": False, 
            "model_prompt_spec": {
                "preamble": preamble # Puxa o texto formatado acima
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