from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

def adicionar_watermark(arquivo_imagem, texto):
    try:
        # Image.open do Pillow é inteligente:
        # Ele aceita tanto caminho (str) quanto arquivo aberto (file-like object do S3)
        img = Image.open(arquivo_imagem).convert("RGBA")
        
        # Cria a camada de texto (Marca d'água)
        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)
        
        # Tenta carregar fonte ou usa padrão
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except:
            font = ImageFont.load_default()

        # Posiciona o texto (Ex: Canto inferior direito)
        # Ajuste a posição conforme seu gosto
        largura, altura = img.size
        # Usando textbbox para calcular tamanho do texto (Pillow moderno)
        bbox = draw.textbbox((0, 0), texto, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = largura - text_width - 20
        y = altura - text_height - 20

        # Desenha o texto semi-transparente
        draw.text((x, y), texto, font=font, fill=(255, 255, 255, 128))

        # Combina as imagens
        watermarked = Image.alpha_composite(img, txt_layer)
        
        # Converte de volta para WebP ou RGB para salvar
        if watermarked.mode in ("RGBA", "P"):
            watermarked = watermarked.convert("RGB")

        # Salva em memória
        buffer = BytesIO()
        watermarked.save(buffer, format="WEBP", quality=85)
        return buffer

    except Exception as e:
        print(f"Erro no serviço de watermark: {e}")
        return None