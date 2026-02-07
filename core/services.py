from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os
from django.conf import settings

def adicionar_watermark(arquivo_imagem, texto):
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