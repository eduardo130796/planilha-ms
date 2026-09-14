# Conversor eSocial – Folha Ordinária

Aplicação local em **Python + Streamlit** para automação e conversão de folhas de pagamento ordinárias no formato exigido pela plataforma do eSocial (`templates/esocial.xlsx`).

---

## 🚀 Como Executar o Projeto

1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Execute a aplicação Streamlit:
   ```bash
   streamlit run app.py
   ```

3. Para rodar a suíte de testes unitários:
   ```bash
   python -m pytest
   ```

---

## 📊 1. Estrutura da Folha de Entrada (Referência)

A aplicação suporta planilhas com uma ou múltiplas abas. As colunas identificadas nas folhas de pagamento de referência incluem:

* `Nome` / `Nome do Residente / Médico` / `Nome do Residente / Profissional`
* `CPF` / `N° CPF`
* `Data de Nascimento` / `Data Nascimento` / `Nascimento`
* `Valor Bruto` / `Valor Inicial / Bolsa (R$)`
* `Valor Líquido` / `Valor Atualizado (R$)`
* `CBO` / `Perfil de Residência` / `Tipo Residência` / `Tipo de Residência`
* `INSS` / `Patronal` / `Desconto INSS`

---

## 🎯 2. Estrutura do Modelo de Saída (`templates/esocial.xlsx`)

O modelo final exigido pela plataforma para importação possui rigorosamente as seguintes 7 colunas, com formatação celular em **Geral** e aba intitulada `E-Social`:

| Coluna | Descrição | Formato |
| :--- | :--- | :--- |
| `cpf` | CPF do beneficiário (11 dígitos, apenas números) | Geral (Texto) |
| `nome` | Nome completo do beneficiário (Maiúsculas, higienizado) | Geral (Texto) |
| `data_nascimento` | Data de nascimento no formato `DD/MM/YYYY` | Geral (Texto) |
| `total_bruto` | Valor bruto da remuneração | Geral (Decimal) |
| `total_liquido` | Valor líquido recebido | Geral (Decimal) |
| `cbo` | Código ou perfil CBO | Geral (Texto/Número) |
| `inss` | Valor da contribuição/desconto INSS | Geral (Decimal) |

---

## 🗺️ 3. Mapa de Conversão (Entrada → Saída)

| Coluna da Folha Ordinária | Coluna eSocial | Regra de Transformação |
| :--- | :--- | :--- |
| `CPF` / `cpf` / `N° CPF` | `cpf` | Remoção de `.`, `-` e espaços. Preenchimento com zeros à esquerda até 11 dígitos. |
| `Nome` / `Nome do Residente` | `nome` | Remoção de espaços duplos, iniciais, finais, quebras de linha e caracteres invisíveis. Conversão para maiúsculas (UPPERCASE). |
| `Data de Nascimento` / `Nascimento` | `data_nascimento` | Padronização para a string `DD/MM/YYYY`. |
| `Valor Bruto` / `Bolsa` | `total_bruto` | Remoção de `R$` e conversão para decimal (`0.00`). |
| `Valor Líquido` / `Liquido` | `total_liquido` | Remoção de `R$` e conversão para decimal (`0.00`). |
| `CBO` / `Perfil de Residência` | `cbo` | Trim e limpeza de espaços. |
| `INSS` / `Patronal` | `inss` | Remoção de `R$` e conversão para decimal (`0.00`). |

---

## 🧹 4. Regras de Higienização Automatizada

1. **Nomes**:
   - Remoção de espaços no início e final (`strip()`).
   - Substituição de múltiplos espaços e quebras de linha (`\n`, `\r`) por um único espaço.
   - Remoção de caracteres invisíveis Unicode (`\xa0`, `\u200b`, `\uFEFF`).
   - Conversão para letras MAIÚSCULAS mantendo acentuação intacta.
2. **CPF**:
   - Remoção de qualquer caractere não numérico.
   - Preenchimento com zeros à esquerda (até 11 dígitos).
   - Tratado estritamente como string para evitar perda de zeros.
3. **Datas**:
   - Normalização de múltiplos formatos (ISO, datetime, serial Excel) para `DD/MM/YYYY`.

---

## 🔍 5. Validações Implementadas

* **Validação Matemática de CPF**: Checagem de 11 dígitos, verificação contra sequências numéricas idênticas (`111.111.111-11`) e cálculo oficial dos 2 dígitos verificadores (DV).
* **Validação de Data de Nascimento**: Checagem de formato `DD/MM/YYYY`, datas inexistentes no calendário (ex: `31/02/2024`), ano mínimo (`1900`) e proibição de datas futuras.
* **Detecção de Duplicidade**: Identificação de CPFs duplicados na mesma aba informando as linhas envolvidas.
* **Campos Obrigatórios**: Notificação de Nomes, CPFs ou Datas vazias.
* **Classificação de Status**:
  * 🔴 **ERRO_CRITICO**: Impede a geração do arquivo. Deve ser corrigido na tela.
  * 🟡 **CONFERIR**: Alerta de divergência (ex: em relação à folha anterior) que exige aprovação ou correção.
  * 🟢 **OK / CONFERIDO**: Registro liberado.

---

## 📜 6. Regras de Comparação com Folha Anterior

* Opcionalmente, o usuário pode carregar a folha do mês anterior para cruzamento.
* O cruzamento é realizado utilizando o **CPF** como chave primária.
* Identifica alterações de `Nome` (🟡 Alerta) e `Data de Nascimento` (🔴 Erro de divergência).
* **Princípio Neutro**: A folha anterior é tratada como referência histórica. O sistema apresenta o alerta para conferência sem presumir erro absoluto.

---

## 🔒 7. Controle de Liberação e Exportação

* O botão **`⬇️ GERAR ARQUIVO ESOCIAL`** fica bloqueado (`🔒 ARQUIVO BLOQUEADO`) enquanto houver erros críticos (🔴) ou pendências não analisadas (🟡).
* A aprovação (`[ ✅ Aprovar atual ]`) ou correção (`[ 💾 Aplicar correção ]`) direta na tela libera o registro (`🟢 CONFERIDO`).
* O arquivo gerado respeita rigorosamente a estrutura, ordem e quantidade de colunas do `templates/esocial.xlsx`.
* Processamento em lote de múltiplas abas gera arquivos individuais e permite o download consolidado em um pacote `.zip`.
