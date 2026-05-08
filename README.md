<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![Unlicense License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/alissonpef/Newsletter-Curator">
    <img src="newsletter-curator.png" alt="Logo">
  </a>

  <h3 align="center">Hermes Newsletter Curator (v3)</h3>

  <p align="center">
    Um pipeline editorial premium para curadoria de newsletters financeiras com busca semântica.
    <br />
    <a href="https://github.com/alissonpef/Newsletter-Curator"><strong>Explorar código »</strong></a>
    <br />
    <br />
    <a href="https://github.com/alissonpef/Newsletter-Curator/issues">Reportar Bug</a>
    &middot;
    <a href="https://github.com/alissonpef/Newsletter-Curator/issues">Sugerir Funcionalidade</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Sumário</summary>
  <ol>
    <li>
      <a href="#📋-sobre-o-projeto">Sobre o Projeto</a>
      <ul>
        <li><a href="#funcionalidades-principais">Funcionalidades Principais</a></li>
      </ul>
    </li>
    <li>
      <a href="#🚀-como-começar">Como Começar</a>
      <ul>
        <li><a href="#pré-requisitos">Pré-requisitos</a></li>
        <li><a href="#instalação">Instalação</a></li>
      </ul>
    </li>
    <li><a href="#🛠️-uso">Uso</a></li>
    <li><a href="#🤝-contribuindo">Contribuindo</a></li>
    <li><a href="#📧-contato">Contato</a></li>
  </ol>
</details>

---

## 📋 Sobre o Projeto

O **Hermes v3** é a evolução definitiva do curador de newsletters. O sistema atua como um editor humano de alta performance: lê seus e-mails, sintetiza um "Resumo Executivo" coeso e gerencia todo o seu histórico através de uma base de conhecimento vetorial.

### Funcionalidades Principais:
- **Síntese Editorial (LLM):** Uso do Ollama para redigir textos contínuos e fluidos, eliminando a fragmentação de notícias repetidas.
- **Busca Vetorial Semântica:** Integração com **ChromaDB** para pesquisar conceitos e temas em todo o histórico de newsletters (ex: "impacto da Petrobras no IPCA").
- **Interface Premium (Editorial Look):** Dashboard web com estética de revista de luxo, centralização inteligente e design responsivo (18px grid).
- **Podcast & PDF:** Geração automatizada de áudio TTS e relatórios PDF minimalistas para consumo em qualquer lugar.
- **Pipeline Automatizado:** Scripts robustos para processamento diário e gerenciamento do servidor.

---

## 🚀 Como Começar

### Pré-requisitos
- **Python 3.11+**
- **Ollama** (necessário para síntese e embeddings vetoriais)
- **ChromaDB** (instalado automaticamente via dependências)

### Instalação

1. Clone o repositório:
   ```sh
   git clone https://github.com/alissonpef/Newsletter-Curator.git
   ```
2. Instale as dependências e prepare o ambiente:
   ```sh
   python -m venv .venv
   source .venv/bin/activate
   pip install .
   ```

3. Configure o arquivo `.env`:
   ```env
   IMAP_HOST=imap.gmail.com
   IMAP_USERNAME=seu_email@gmail.com
   IMAP_PASSWORD=sua_senha_app
   OLLAMA_CHAT_MODEL=qwen2.5:7b
   OLLAMA_EMBED_MODEL=mxbai-embed-large
   ```

---

## 🛠️ Uso

O Hermes v3 agora conta com scripts de automação que garantem que todos os serviços (como Ollama) estejam prontos antes da execução.

### 1. Dashboard Web & Memória (Recomendado)
Para iniciar a interface editorial e usar a **Busca Vetorial**:
```sh
./hermes_web.sh
```
Acesse em: `http://127.0.0.1:8787`

### 2. Rodar o Pipeline de Geração (Terminal)
Para processar e sintetizar as newsletters do dia:
```sh
# Hoje
./hermes_run.sh

# Data específica
./hermes_run.sh 25/04/2026
```

---

## 🤝 Contribuindo

Contribuições são bem-vindas para manter a versão v3 limpa e direta.

1. Fork o projeto
2. Crie sua Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a Branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

---

## 📧 Contato

**Alisson Pereira Ferreira**  
LinkedIn: [https://www.linkedin.com/in/alisson-pereira-ferreira/](https://www.linkedin.com/in/alisson-pereira-ferreira/)  
E-mail: [alissonpef@gmail.com](mailto:alissonpef@gmail.com)  

Link do Projeto: [https://github.com/alissonpef/Newsletter-Curator](https://github.com/alissonpef/Newsletter-Curator)

---

<p align="right">(<a href="#readme-top">voltar ao topo</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/alissonpef/Newsletter-Curator.svg?style=for-the-badge
[contributors-url]: https://github.com/alissonpef/Newsletter-Curator/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/alissonpef/Newsletter-Curator.svg?style=for-the-badge
[forks-url]: https://github.com/alissonpef/Newsletter-Curator/network/members
[stars-shield]: https://img.shields.io/github/stars/alissonpef/Newsletter-Curator.svg?style=for-the-badge
[stars-url]: https://github.com/alissonpef/Newsletter-Curator/stargazers
[issues-shield]: https://img.shields.io/github/issues/alissonpef/Newsletter-Curator.svg?style=for-the-badge
[issues-url]: https://github.com/alissonpef/Newsletter-Curator/issues
[license-shield]: https://img.shields.io/github/license/alissonpef/Newsletter-Curator.svg?style=for-the-badge
[license-url]: https://github.com/alissonpef/Newsletter-Curator/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://www.linkedin.com/in/alisson-pereira-ferreira/