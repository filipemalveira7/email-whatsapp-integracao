# Playbook — 5 campanhas prontas

Templates de copy + sequência de disparo + horário ouro pra cada cenário. A copy aqui é **estrutural** (esqueleto). Você adapta com seu produto, seu link, seu tom. Não dispare estes textos como estão — adapte.

> **Aviso obrigatório LGPD**: toda mensagem Marketing precisa de opt-out claro. Padrão sugerido no rodapé: `Pra parar de receber, responde SAIR.`

---

## 1. Aquecimento de turma / lançamento (D-7 a D-1)

**Objetivo:** preparar a base, aumentar consumo do conteúdo orgânico, gerar antecipação.

**Cadência:** 1 mensagem/dia, sempre 9h30 ou 14h30.

**D-7 — Curiosidade**
```
*Algo grande chegando*

Nos últimos meses a gente desenvolveu uma forma de [BENEFÍCIO BÁSICO]
que muda como você [TAREFA].

Na semana que vem libero o passo a passo gratuito. Fica de olho.

Pra parar, responde SAIR.
```

**D-5 — Prova social**
```
A [NOME DA PESSOA / CLIENTE] aplicou o método e em [TEMPO] já tinha
[RESULTADO ESPECÍFICO COM NÚMERO].

Quer ver como? Responde *quero* aqui no privado.

(Pra parar, responde SAIR.)
```

**D-3 — Mecanismo único**
```
A diferença do nosso método pros outros 3 do mercado é uma só:

[O QUE TE FAZ DIFERENTE EM 1 LINHA]

É isso que destrava o resultado. Quarta tem aula gratuita. Liberei
inscrições. Link 👇

[LINK]

Responde SAIR pra parar.
```

**D-1 — Lembrete**
```
Amanhã 20h. Aula gratuita. [TEMA]

Se você ainda não pegou seu acesso 👇
[LINK]

(SAIR pra parar de receber.)
```

**Disparo programado:** use `python3 disparo.py agendar --when "2026-MM-DDT09:30" --text-file copy_d-7.txt --csv ./grupos.csv` pra cada dia.

---

## 2. Oferta direta (carrinho aberto)

**Objetivo:** fechar venda. Janela típica: 5-7 dias com 8-12 disparos crescendo em urgência.

**D0 — Abertura**
```
*Carrinho aberto.* 🔓

[NOME DO PRODUTO] entrou na promoção até [DATA].

Tudo o que você precisa pra [BENEFÍCIO PRINCIPAL]:
- [BENEFÍCIO 1]
- [BENEFÍCIO 2]
- [BENEFÍCIO 3]

Garante a sua vaga 👇
[LINK]

Pra parar, SAIR.
```

**D1 — Bônus / risco invertido**
```
Quem entrar até hoje 23h59 leva [BÔNUS ESPECÍFICO COM VALOR].

Pra que serve? [1 LINHA].

Garantia de [DIAS] dias — não gostou, devolvo seu dinheiro.

[LINK]

(SAIR pra parar.)
```

**D5 — Urgência REAL**
```
*48h pra fechar.*

[NÚMERO REAL] de pessoas já entraram. Restam [NÚMERO REAL] vagas.

Depois disso, sobe pra [PREÇO MAIOR] e tira o bônus.

[LINK]

(SAIR pra parar.)
```

**D6 — Último aviso**
```
24h.

[LINK]

(SAIR pra parar.)
```

**D7 — Fechamento**
```
Encerrei.

Quem fechou — bem-vindo. Acesso chegando no e-mail nas próximas 2h.
Quem ficou de fora — ano que vem tem mais.

Obrigado.
```

> **CDC art. 37**: a urgência precisa ser real. Se você diz "restam 5 vagas", precisa restar 5 mesmo.

---

## 3. Reativação de base fria

**Objetivo:** trazer de volta quem sumiu.

**Disparo único — sábado 10h ou domingo 11h** (horário em que pessoa fria abre WhatsApp por tédio).

```
Oi! 👋

Faz tempo que a gente não conversa por aqui. Tô passando pra avisar
que [NOVIDADE GENUÍNA — não inventa pra forçar].

Se ainda faz sentido pra você, dá uma olhada 👇
[LINK]

Se não faz mais — sem problema, responde *SAIR* que eu paro de
mandar pra você.

Abraço.
```

**Métrica de sucesso:** conversão >2% reativação considera bom. Abaixo de 0,5% = base queimada, troca a estratégia.

---

## 4. Pesquisa de feedback (alto valor, baixo custo)

**Objetivo:** coletar dados pra melhorar produto + reabrir conversa.

**Disparo único, dias úteis 14h.**

```
*Pesquisa rápida — 30 segundos.*

Quero entender o que prende você de [TAREFA RELACIONADA AO PRODUTO].

Responde aqui só com o NÚMERO:

1️⃣ Não tenho tempo
2️⃣ Não sei por onde começar
3️⃣ Já tentei e não funcionou
4️⃣ Não acho que vale o investimento
5️⃣ Outro (escreve em 1 linha)

Tua resposta direciona o próximo conteúdo gratuito que vou liberar.

Obrigado!

(SAIR pra parar.)
```

**Pós-pesquisa:** segmenta a base pelos números recebidos e dispara conteúdo específico pra cada bucket.

---

## 5. Convite pra evento ao vivo (live, workshop, webinar)

**Objetivo:** maximizar presentes na live.

**Cadência: D-3 / D-1 / D0 manhã / D0 1h antes / D0 ao vivo.**

**D-3 — Convite**
```
[DATA] tem live.

Tema: [TÍTULO IMPACTANTE — promessa específica + tempo]

Quem participa ao vivo ganha [BÔNUS ESPECÍFICO PRA AO VIVO].

Reserva sua vaga 👇
[LINK]

(SAIR pra parar.)
```

**D0 manhã**
```
HOJE 20h.

[TEMA]

[LINK]

(SAIR pra parar.)
```

**D0 — 1h antes**
```
Em 1h.

[LINK DIRETO DA SALA]

Te vejo lá.

(SAIR pra parar.)
```

**D0 — ao vivo (gatilho FOMO)**
```
*Tô ao vivo agora.* 🔴

[O QUE ESTÁ ACONTECENDO BEM AGORA — frase forte]

Entra 👇
[LINK]
```

> Live em si NÃO leva opt-out (quem entrou no link já optou). Mas a mensagem que disparou pra base sim.

---

---

## 6. X1 — abordagem 1:1 personalizada (alto valor, alto risco)

**Objetivo:** abordar contatos individuais com mensagem que parece escrita à mão. Convém pra: pós-evento, trial expirado, lead que pediu orçamento e sumiu, recuperação de carrinho, follow-up comercial humano.

**Volume seguro x1: 200-300 contatos/dia, fragmentado em 2-3 janelas de horário ouro.**

### CSV de contatos (`contatos.csv`)

```csv
phone,name,tag
5511999990001,Maria Silva,trial_expirado
5521988880002,João Souza,carrinho_abandonado
5531977770003,Ana Costa,evento_dia_15
```

### Copy x1 — Follow-up de orçamento

```
Oi {{first_name}}, tudo bem?

Aqui é a [SEU NOME] da [EMPRESA]. Você pediu orçamento de
[PRODUTO/SERVIÇO] semana passada e eu não voltei pra fechar contigo.

Tô passando pra avisar 2 coisas:

1. A condição que conversamos vale até [DATA]
2. Se não fizer sentido agora, sem problema — me responde *pode parar*
   que eu paro de te incomodar.

Posso te mandar a proposta atualizada agora?
```

### Copy x1 — Recuperação de carrinho

```
Oi {{first_name}}!

Vi que você começou a comprar [PRODUTO] aqui no site mas não finalizou.
Algum problema com o pagamento? Posso ajudar?

Se mudou de ideia, sem stress — responde *parar* que eu paro.
```

### Copy x1 — Pós-evento

```
{{first_name}}, valeu por participar do [EVENTO] ontem!

Anota aí o link pra material complementar: [LINK]

Qualquer dúvida sobre o que rolou, me chama aqui mesmo.

(Pra parar de receber, responde *SAIR*.)
```

### Comando

```bash
python3 disparo.py x1 \
  --contatos contatos.csv \
  --text-file copy_x1.txt \
  --confirmed-test \
  --delay 75 --jitter 0.2 --retry 3
```

Ou via Claude Code: `> x1: oi {{first_name}}, tudo bem? aqui é a [seu nome]...`

### Regras anti-ban x1

- **NUNCA** copy idêntica em mais de 50 envios — o WhatsApp detecta. Use `{{first_name}}` no mínimo.
- Copy curta (≤4 linhas) tem taxa de bloqueio menor.
- Mídia em x1: só pra contatos que JÁ se relacionaram com você (não desconhecido). Foto de produto pra lead frio = denúncia.
- Horário: 9h-11h é o ouro absoluto pra x1 — taxa de resposta 3x maior que à noite.
- Acompanhe respostas em tempo real e desliga o disparo se ver 5+ "quem é você?" em sequência.

---

## Checklist anti-ban antes de qualquer campanha

- [ ] `.env` preenchido e funcionando (`python3 health_check.py` 🟢)
- [ ] `grupos.csv` revisado — só grupos onde tenho permissão de admin/membro pra postar
- [ ] `blacklist.txt` atualizado com opt-outs recebidos
- [ ] Copy revisada por humano — sem promessa enganosa, com SAIR no rodapé
- [ ] Mídia local validada (não URL)
- [ ] Horário escolhido está no quadro OURO/PRATA (não madrugada, não domingo)
- [ ] Teste no número pessoal feito e validado
- [ ] Delay ≥ 60s configurado
- [ ] Janela de monitoramento agendada nas 4h seguintes ao disparo (pra responder rápido se alguém engajar)
