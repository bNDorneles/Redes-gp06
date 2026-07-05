# Regras de Implementação — Projeto Redes (UDP Echo/Chat)

Este documento define as regras obrigatórias de código para qualquer
implementação neste repositório. O agente deve seguir estas regras
sem exceção, mesmo que o plano aprovado não as mencione explicitamente.

## 1. Escopo e Fidelidade ao Plano

- Implementar exatamente o que está no plano aprovado da issue. Não adicionar
  funcionalidades, arquivos ou dependências fora do escopo descrito.
- Não modificar módulos de outras issues (ex: `src/echo/` ao trabalhar na
  issue de chat, e vice-versa).
- Em caso de ambiguidade entre o plano e a issue original, a issue prevalece.
  Se restar dúvida, parar e perguntar antes de decidir sozinho.

## 2. Princípios de Design

- **Clean Code**: nomes descritivos e sem abreviações obscuras, funções
  pequenas e com uma única responsabilidade, sem efeitos colaterais ocultos.
- **SOLID**: especialmente Single Responsibility (cada função/classe faz uma
  coisa) e Dependency Inversion quando fizer sentido (ex: injetar o socket
  em vez de criar dependência rígida, quando isso não adicionar complexidade
  desnecessária para o escopo acadêmico).
- Evitar duplicação de lógica entre client e server (ex: extrair
  serialização/desserialização de mensagens JSON para uma função ou módulo
  compartilhado, se ambos os arquivos precisarem dela).
- Sem "magic numbers" ou strings soltas no meio do código: usar constantes
  nomeadas (ex: `DEFAULT_PORT = 5001`, `SOCKET_TIMEOUT_SECONDS = 2.0`,
  `MESSAGE_TYPE_JOIN = "JOIN"`).
- Sem funções ou classes "genéricas demais" para o escopo. Simplicidade
  acima de abstração especulativa (YAGNI) — este é um projeto acadêmico
  de Redes, não uma biblioteca de produção.

## 3. Tipagem e Documentação

- **Type hints obrigatórios** em todos os parâmetros e retornos de função,
  incluindo tipos compostos (`dict[str, str]`, `tuple[str, int]`,
  `Optional[str]`, etc.).
- **Docstrings obrigatórias em todas as funções e classes**, no padrão
  **Google style**, escritas em **português**. Exemplo:

```python
  def registrar_cliente(endereco: tuple[str, int], apelido: str) -> bool:
      """Registra um novo cliente no chat.

      Args:
          endereco: Par (ip, porta) de origem do cliente.
          apelido: Nome escolhido pelo cliente.

      Returns:
          True se o registro foi bem-sucedido, False se o apelido
          já estava em uso por outro endereço.
      """
```

- Identificadores de código (nomes de variáveis, funções, classes, módulos)
  **em inglês**. Docstrings **em português**.
- Mensagens exibidas ao usuário final no terminal podem ser em português
  (é a interface do chat).

## 4. Comentários

- **Não escrever comentários que descrevem o óbvio** ou que qualquer
  programador entenderia lendo o código (ex: `# incrementa contador`,
  `# loop principal`, `# fecha o socket`).
- Comentários são permitidos apenas para justificar decisões não óbvias,
  como:
  - Por que um `settimeout` tem um valor específico.
  - Por que uma exceção específica está sendo tratada de um jeito
    aparentemente estranho (ex: contornos de compatibilidade Windows/cp1252).
  - Trade-offs conhecidos e aceitos (ex: a limitação de interleaving do
    `input()` já discutida no plano).
- Se o código precisa de um comentário para ser entendido, preferir
  refatorar (renomear, extrair função) antes de comentar.

## 5. Tratamento de Erros

- Nunca usar `except:` genérico. Sempre capturar exceções específicas
  (`json.JSONDecodeError`, `UnicodeDecodeError`, `socket.timeout`,
  `KeyError`, etc.).
- Toda falha esperada (datagrama malformado, apelido duplicado, campo
  ausente) deve ser tratada de forma explícita e não deve encerrar o
  processo, conforme já definido no plano da issue.
- Falhas inesperadas não devem ser silenciadas sem motivo — se for
  necessário um "catch-all" de segurança, registrar a exceção
  (`print` ou `logging`) antes de continuar, nunca engolir silenciosamente.

## 6. Formatação e Estilo

- Formatação via **Black** (configuração padrão, sem customização de
  `line-length` salvo necessidade justificada).
- Imports organizados: biblioteca padrão primeiro, depois dependências
  externas, depois módulos locais — cada grupo separado por linha em branco.
- Sem código morto: nenhuma função, import ou variável não utilizada.
- Sem `print` de debug esquecido no código final.

## 7. Testes

- **Não criar nenhum arquivo de teste automatizado** (`pytest`, `unittest`
  ou qualquer outro), mesmo que isso reduza a cobertura formal. Essa é uma
  restrição explícita do critério de aceite da issue.
- Toda validação deve ser feita exclusivamente pelo roteiro de testes
  manuais já definido no plano aprovado.

## 8. Git e Entrega

- Branch e PR seguindo exatamente o que a issue especifica (nome da branch,
  base `develop`).
- Commits atômicos, seguindo Conventional Commits (`feat:`, `fix:`,
  `refactor:`, `docs:`, etc.), um commit por unidade lógica de mudança —
  não um único commit gigante com tudo.
- Nenhuma dependência externa nova sem necessidade clara (o projeto deve
  rodar com Python padrão + biblioteca padrão, salvo se algo já estiver
  definido no plano).

## 9. Antes de Declarar Concluído

- Rodar mentalmente (ou de fato, se possível) cada item do roteiro de
  testes manuais do plano antes de reportar a tarefa como pronta.
- Não declarar "implementação concluída" sem confirmar que todos os
  critérios de aceite da issue foram atendidos um a um.