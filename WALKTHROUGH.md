# Walkthrough: Automação TikTok Shop Affiliate com Telegram

Automação para busca de criadores no TikTok Shop Affiliate, captura de 2 prints (página inteira + hover em categorias) e envio direto pelo Telegram.

---

## 📁 Estrutura de Arquivos

- `bot.py`: Script principal com toda a lógica (navegador persistente via Playwright + bot Telegram nativo via `requests`).
- `requirements.txt`: Dependências do projeto (`playwright`, `requests`).
- `chrome_profile/`: Pasta gerada automaticamente onde ficam salvos os cookies e a sessão de login.

---

## 🚀 Como Usar

### 1. Fazer o Login Inicial (apenas na 1ª vez)
Execute no terminal:
```powershell
python bot.py --login
```
- Uma janela do navegador (Edge/Chrome) será aberta no portal do TikTok Shop Affiliate.
- Faça o login normalmente com sua conta.
- Quando o painel carregar, volte ao terminal e pressione **ENTER** para salvar a sessão na pasta `./chrome_profile`.

---

### 2. Teste Rápido pelo Terminal (Opcional)
Se quiser testar a captura de um perfil sem abrir o Telegram:
```powershell
python bot.py wesllenry
```
Dois arquivos serão gerados na pasta do projeto:
- `print1_full_wesllenry.png` (página inteira sem cortes de scroll)
- `print2_hover_wesllenry.png` (cabeçalho com o balão/tooltip de categorias aberto)

---

### 3. Rodar com o Bot do Telegram
Crie um bot no Telegram com o [@BotFather](https://t.me/BotFather) e pegue o seu token.

No terminal PowerShell, defina a variável e inicie o bot:
```powershell
$env:TELEGRAM_TOKEN="SEU_TOKEN_AQUI"

# Opcional (para responder apenas ao seu ID):
# $env:ALLOWED_CHAT_ID="SEU_CHAT_ID"

python bot.py
```

Agora basta abrir a conversa com seu bot no Telegram e enviar o `@` ou nome do criador (ex: `@wesllenry`). Ele responderá automaticamente com os 2 prints!

