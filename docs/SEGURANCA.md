# Segurança e proteção dos dados

- **Repositório público**: o `.gitignore` bloqueia `dados/`, bancos SQLite, runtime, Ollama, modelos e relatórios gerados. Mesmo assim, nunca arraste arquivos de caso para o site do GitHub. Use apenas os exemplos fictícios para demonstrar problemas.
- **Servidor**: escuta somente em `127.0.0.1`; exige a chave de sessão exibida no terminal (cookie `HttpOnly`, `SameSite=Strict`); confere o cabeçalho `Host`; recusa requisições de escrita sem o cabeçalho próprio da interface; envia `Content-Security-Policy` restritiva e não carrega nada da internet.
- **IA**: somente `http://127.0.0.1`, sem proxies, modelos de nuvem recusados. O conteúdo dos documentos é delimitado como dado e não como instrução.
- **Originais**: guardados sem alteração, com SHA-256 conferível na aba Fontes. A importação recusa original cujo SHA-256 não confere.
- **Auditoria**: ações relevantes ficam registradas por caso.
- **Atualizador**: só acessa `github.com`/`codeload.github.com` por HTTPS, mostra o SHA-256 do pacote, recusa caminhos suspeitos, faz cópia da versão anterior e não toca nas pastas protegidas.
- **Limites**: a identificação de usuário é declarada na tela. Proteja o computador com login individual, criptografia de disco e permissões de pasta conforme as normas da instituição. Faça cópia de segurança de `dados/` em mídia autorizada.
