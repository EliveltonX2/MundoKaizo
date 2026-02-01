# core/services.py
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import os
from io import BytesIO
from django.conf import settings

def adicionar_watermark(imagem_path, texto_usuario):
    """
    Abre a imagem do disco, adiciona marca d'água e retorna um objeto BytesIO.
    """
    try:
        # 1. Abrir imagem original (Converte para RGBA para suportar transparência na edição)
        base_image = Image.open(imagem_path).convert("RGBA")
        
        # Cria uma camada transparente do mesmo tamanho da imagem base
        txt_layer = Image.new("RGBA", base_image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)
        
        # 2. Configurar Fonte
        # Tenta pegar uma fonte arial ou usa padrão. 
        # No futuro (Deploy), colocaremos uma fonte .ttf na pasta static.
        try:
            font_size = int(base_image.width / 20) # Tamanho dinâmico (5% da largura)
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()

        # 3. Desenhar o Texto (Padrão Diagonal e Repetido)
        width, height = base_image.size
        text_width = int(width / 2) # estimativa
        text_height = int(height / 4)
        
        # Cor do texto: Cinza claro semi-transparente (R, G, B, Alpha)
        # Alpha 50 = bem suave. 128 = médio.
        text_color = (128, 128, 128, 80) 

        # Loop para criar um padrão repetido (Grid 3x3 para cobrir a página)
        for x in range(0, width, int(width/2)):
            for y in range(0, height, int(height/4)):
                draw.text((x, y), texto_usuario, font=font, fill=text_color)

        # Opcional: Rotacionar a camada de texto (requer cálculo complexo de canvas, 
        # vamos manter simples/reto por enquanto para garantir performance)

        # 4. Fundir as camadas (Composite)
        watermarked_image = Image.alpha_composite(base_image, txt_layer)
        
        # 5. Converter de volta para RGB (remove canal alpha para salvar como JPEG)
        watermarked_image = watermarked_image.convert("RGB")

        # 6. Salvar em memória (BytesIO)
        output_io = BytesIO()
        watermarked_image.save(output_io, format='JPEG', quality=85)
        output_io.seek(0) # Retorna o ponteiro para o início do arquivo

        return output_io

    except Exception as e:
        print(f"Erro no processamento de imagem: {e}")
        return None