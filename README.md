<a id="readme-top"></a>

<!-- ESCUDOS DO PROJETO -->

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]

<!-- LOGOTIPO DO PROJETO -->
<br />
<div align="center">
  <a href="https://github.com/alissonpef/newsletter_curator">
    <img src="assets/newsletter-curator.png" alt="Logo" width="120" height="120">
  </a>

  <h3 align="center">Hermes Newsletter Curator</h3>

  <p align="center">
    Um pipeline editorial premium para curadoria de newsletters financeiras com busca semântica.
    <br />
    <a href="https://github.com/alissonpef/newsletter_curator"><strong>Explore a documentação »</strong></a>
    <br />
    <br />
    <a href="https://github.com/alissonpef/newsletter_curator/issues">Reportar Bug</a>
    &middot;
    <a href="https://github.com/alissonpef/newsletter_curator/issues">Solicitar Recurso</a>
  </p>
</div>

<!-- ÍNDICE -->
<details>
  <summary>Índice</summary>
  <ol>
    <li>
      <a href="#sobre-o-projeto">Sobre O Projeto</a>
      <ul>
        <li><a href="#construído-com">Construído Com</a></li>
      </ul>
    </li>
    <li>
      <a href="#começando">Começando</a>
      <ul>
        <li><a href="#pré-requisitos">Pré-requisitos</a></li>
        <li><a href="#instalação">Instalação</a></li>
      </ul>
    </li>
    <li><a href="#uso">Uso</a></li>
    <li><a href="#contribuindo">Contribuindo</a></li>
    <li><a href="#licença">Licença</a></li>
    <li><a href="#contato">Contato</a></li>
  </ol>
</details>

<!-- SOBRE O PROJETO -->

## Sobre O Projeto

O **Hermes** é a evolução definitiva do curador de newsletters. O sistema atua como um editor humano de alta performance: lê seus e-mails, sintetiza um "Resumo Executivo" coeso e gerencia todo o seu histórico através de uma base de conhecimento vetorial.

Aqui está o porquê:

- **Síntese Editorial (LLM):** Uso do Ollama para redigir textos contínuos e fluidos, eliminando a fragmentação de notícias repetidas.
- **Busca Vetorial Semântica:** Integração com **ChromaDB** para pesquisar conceitos e temas em todo o histórico de newsletters (ex: "impacto da Petrobras no IPCA").
- **Interface Premium (Editorial Look):** Dashboard web com estética de revista de luxo, centralização inteligente e design responsivo (18px grid).
- **Podcast & PDF:** Geração automatizada de áudio TTS e relatórios PDF minimalistas para consumo em qualquer lugar.
- **Pipeline Automatizado:** Scripts robustos para processamento diário e gerenciamento do servidor.

<p align="right">(<a href="#readme-top">voltar ao topo</a>)</p>

### Construído Com

Esta seção lista os principais frameworks, linguagens e bibliotecas que dão vida a este projeto:

- [![Python][Python.org]][Python-url]
- [![FastAPI][FastAPI.tiangolo.com]][FastAPI-url]
- [![ChromaDB][Chroma.db]][Chroma-url]
- [![Ollama][Ollama.com]][Ollama-url]
- [![Jinja2][Jinja.palletsprojects.com]][Jinja-url]
- [![FPDF2][FPDF2.github.io]][FPDF-url]

<p align="right">(<a href="#readme-top">voltar ao topo</a>)</p>

<!-- COMEÇANDO -->

## Começando

Para ter uma cópia local rodando e funcionando, siga os passos simples abaixo.

### Pré-requisitos

Este projeto exige Python 3.11+ e a ferramenta `uv` para o gerenciamento ágil de dependências e ambiente virtual.

- Instale o `uv` (caso ainda não o tenha):
  ```sh
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Ollama**: Certifique-se de ter o Ollama instalado localmente e executando com os modelos necessários (`qwen2.5:7b` e `mxbai-embed-large` ou equivalentes).

### Instalação

1. Clone o repositório:
   ```sh
   git clone https://github.com/alissonpef/newsletter_curator.git
   ```
2. Instale as dependências e configure o ambiente com `uv`:
   ```sh
   uv sync --all-extras --dev
   ```
3. Crie e configure o arquivo `.env` com base no exemplo:
   ```sh
   cp .env.example .env
   ```
4. Edite o arquivo `.env` com suas credenciais de e-mail (IMAP/SMTP) e configurações de modelo.

<p align="right">(<a href="#readme-top">voltar ao topo</a>)</p>

<!-- EXEMPLOS DE USO -->

## Uso

### 1. Iniciar o Dashboard Web (Interface Editorial)

Use o script de inicialização do servidor web (que também garante a inicialização do banco vetorial):
```sh
./hermes_web.sh
```
Ou diretamente com `uv`:
```sh
uv run python -m hermes.main
```
Acesse o painel em: `http://127.0.0.1:8787`

### 2. Rodar o Pipeline de Curação Diária (Terminal)

Para processar manualmente as newsletters do dia atual:
```sh
./hermes_run.sh
```
Ou para uma data específica (DD/MM/AAAA ou AAAA-MM-DD):
```sh
./hermes_run.sh 25/04/2026
```
Ou diretamente com `uv`:
```sh
uv run python -m hermes.cli 2026-04-25
```

<p align="right">(<a href="#readme-top">voltar ao topo</a>)</p>

<!-- CONTRIBUINDO -->

## Contribuindo

As contribuições tornam a comunidade de software livre um local maravilhoso para aprender, inspirar e criar. Qualquer contribuição que você fizer será **extremamente valiosa**.

1. Faça o Fork do Projeto
2. Crie a sua Branch de Funcionalidade (`git checkout -b feature/FuncionalidadeIncrivel`)
3. Commit suas Mudanças (`git commit -m 'Adicione alguma FuncionalidadeIncrivel'`)
4. Faça o Push para a Branch (`git push origin feature/FuncionalidadeIncrivel`)
5. Abra um Pull Request

### Principais contribuidores:

<a href="https://github.com/alissonpef/newsletter_curator/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=alissonpef/newsletter_curator" alt="imagem contrib.rocks" />
</a>

<p align="right">(<a href="#readme-top">voltar ao topo</a>)</p>

<!-- LICENÇA -->

## Licença

Distribuído sob a Licença MIT. Veja o arquivo `LICENSE` para mais informações.

<p align="right">(<a href="#readme-top">voltar ao topo</a>)</p>

<!-- CONTATO -->

## Contato

Alisson Pereira Ferreira - [alissonpef@gmail.com](mailto:alissonpef@gmail.com) - [LinkedIn](https://www.linkedin.com/in/alisson-pereira-ferreira/)

Link do Projeto: [https://github.com/alissonpef/newsletter_curator](https://github.com/alissonpef/newsletter_curator)

<p align="right">(<a href="#readme-top">voltar ao topo</a>)</p>

---

Made with ❤️ by **Alisson Pereira**.

<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/alissonpef/newsletter_curator.svg?style=for-the-badge
[contributors-url]: https://github.com/alissonpef/newsletter_curator/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/alissonpef/newsletter_curator.svg?style=for-the-badge
[forks-url]: https://github.com/alissonpef/newsletter_curator/network/members
[stars-shield]: https://img.shields.io/github/stars/alissonpef/newsletter_curator.svg?style=for-the-badge
[stars-url]: https://github.com/alissonpef/newsletter_curator/stargazers
[issues-shield]: https://img.shields.io/github/issues/alissonpef/newsletter_curator.svg?style=for-the-badge
[issues-url]: https://github.com/alissonpef/newsletter_curator/issues
[license-shield]: https://img.shields.io/github/license/alissonpef/newsletter_curator.svg?style=for-the-badge
[license-url]: https://github.com/alissonpef/newsletter_curator/blob/main/LICENSE
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://www.linkedin.com/in/alisson-pereira-ferreira/

[Python.org]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://www.python.org/
[FastAPI.tiangolo.com]: https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white
[FastAPI-url]: https://fastapi.tiangolo.com/
[Chroma.db]: https://img.shields.io/badge/ChromaDB-fc5603?style=for-the-badge&logo=google-cloud&logoColor=white
[Chroma-url]: https://www.trychroma.com/
[Ollama.com]: https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white
[Ollama-url]: https://ollama.com/
[Jinja.palletsprojects.com]: https://img.shields.io/badge/Jinja2-B81D24?style=for-the-badge&logo=jinja&logoColor=white
[Jinja-url]: https://jinja.palletsprojects.com/
[FPDF2.github.io]: https://img.shields.io/badge/FPDF2-285D4A?style=for-the-badge&logo=pdf&logoColor=white
[FPDF-url]: https://fpdf2.github.io/fpdf2/