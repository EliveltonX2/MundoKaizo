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

        # ... (continua seu código da marca d'água igualzinho) ...
        
        # ... (código do grid de texto) ...

        # Na hora de salvar, mantenha o WebP e Quality 85
    
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

def enviar_mensagem_para_ia(texto_usuario):
    credenciais = obter_credenciais_google()
    
    # Inicializa o cliente de Busca e Conversação
    client = discoveryengine.SearchServiceClient(credentials=credenciais)

    # Configuração do Engine da Kai (Busca em SP)
    # Certifique-se que o DATA_STORE_ID no settings.py seja 'biblioteca-exploradores-kaizo'
    serving_config = f"projects/{settings.VERTEX_PROJECT_ID}/locations/{settings.VERTEX_LOCATION}/collections/default_collection/dataStores/{settings.DATA_STORE_ID}/servingConfigs/default_search"

    # AQUI ENTRA A PERSONA E O GROUNDING NOS PDFs
    content_search_spec = {
        "summary_spec": {
            "summary_result_count": 5,
            "include_citations": False, # Oculta links do Bucket conforme pedido
            "model_prompt_spec": {
                "preamble": """
                Você é a Kai, a inteligência artificial oficial da Kaizo. 
                Sua missão é ser a assistente pedagógica definitiva para professores.
                DIRETRIZES:
                1. Seja vibrante, entusiasta e alegre.
                2. Use prioritariamente os PDFs da Coleção Exploradores e BNCC.
                3. Se o usuário falar '7º ano', entenda como 'Livro 7'.
                4. Entregue caminhos prontos e práticos para a sala de aula.
                """
            },
            "model_spec": {
                "version": "stable" 
            }
        }
    }

    # Monta a requisição que une Busca + IA Generativa
    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=texto_usuario,
        content_search_spec=content_search_spec,
    )

    # Executa a busca e retorna o resumo gerado
    response = client.search(request)
    
    # Retorna o texto gerado com base nos seus documentos
    return response.summary.summary_text