import xml.etree.ElementTree as ET
from langchain_core.documents import Document
from datetime import datetime

class LattesProcessor:
    def __init__(self, xml_path):
        self.xml_path = xml_path
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()
        self.data_ingestao = datetime.now().isoformat()
        
        self.researcher_info = self._extract_global_info()

    def _extract_global_info(self):
        dados_gerais = self.root.find('DADOS-GERAIS')
        
        endereco = dados_gerais.find('ENDERECO/ENDERECO-PROFISSIONAL')
        instituicao = endereco.attrib.get('NOME-INSTITUICAO-EMPRESA', 'Não Informada') if endereco is not None else "Não Informada"

        if dados_gerais is None:
            return None

        return {
            "nome": dados_gerais.attrib.get('NOME-COMPLETO', None),
            "id_lattes": self.root.attrib.get('NUMERO-IDENTIFICADOR', None),
            "atualizacao": self.root.attrib.get('DATA-ATUALIZACAO', None),
            "instituicao": instituicao,
            "source": str(self.xml_path),
            "data_ingestao": self.data_ingestao
        }

    def get_profile_doc(self):
        """
        Gera o documento ÚNICO para a coleção 'researchers_summary'.
        Agrega Resumo + Áreas + Keywords de Projetos/Orientações.
        """
        dados_gerais = self.root.find('DADOS-GERAIS')
        resumo = dados_gerais.find('RESUMO-CV')
        texto_resumo = resumo.attrib.get('TEXTO-RESUMO-CV-RH', '') if resumo is not None else ""

        areas = [a.attrib.get('NOME-DA-AREA-DO-CONHECIMENTO') for a in self.root.findall('.//AREA-DE-ATUACAO')]
        texto_areas = ", ".join(filter(None, areas))

        keywords = []
        for proj in self.root.findall('.//PROJETO-DE-PESQUISA'):
            keywords.append(proj.attrib.get('NOME-DO-PROJETO'))
        for orient in self.root.findall('.//DETALHAMENTO-DA-ORIENTACAO-CONCLUIDA'):
            keywords.append(orient.attrib.get('TITULO-DO-TRABALHO-DE-CONCLUSAO'))
        
        texto_keywords = "; ".join(filter(None, keywords))

        content = (
            f"PERFIL PESQUISADOR: {self.researcher_info['nome']}\n"
            f"INSTITUIÇÃO: {self.researcher_info['instituicao']}\n"
            f"RESUMO: {texto_resumo}\n"
            f"ÁREAS DE ATUAÇÃO: {texto_areas}\n"
            f"TEMAS TRABALHADOS (PROJETOS/ORIENTAÇÕES): {texto_keywords}"
        )

        metadata = self.researcher_info.copy()
        metadata.update({
            "tipo": "perfil",
            "conteudo": content
        })

        return Document(page_content=content, metadata=metadata)

    def _get_projetos(self):
        docs = []
        base_metadata = self.researcher_info.copy()

        for proj in self.root.findall('.//PROJETO-DE-PESQUISA'):
            nome = proj.attrib.get('NOME-DO-PROJETO', 'Sem título')
            desc = proj.attrib.get('DESCRICAO-DO-PROJETO', '')
            ano_inicio = proj.attrib.get('ANO-INICIO', '')
            ano_fim = proj.attrib.get('ANO-FIM', '')
            situacao_raw = proj.attrib.get('SITUACAO', '')

            lista_nomes = []
            nome_responsavel = None
            
            for integrante in proj.findall('./EQUIPE-DO-PROJETO/INTEGRANTES-DO-PROJETO'):
                nome_int = integrante.attrib.get("NOME-COMPLETO")
                if nome_int:
                    lista_nomes.append(nome_int)
                    if integrante.attrib.get("FLAG-RESPONSAVEL", "NAO").upper() == "SIM":
                        nome_responsavel = nome_int

            str_pesquisadores = ", ".join(lista_nomes)
            
            trecho_responsavel = f", sendo o(a) pesquisador(a) {nome_responsavel} o(a) responsável" if nome_responsavel else ""
            
            mapa_situacao = {
                "CONCLUIDO": "concluído",
                "EM_ANDAMENTO": "em andamento",
            }

            str_situacao = mapa_situacao.get(situacao_raw, situacao_raw.lower())

            content = (
                f"O projeto: '{nome}', é integrado pelos pesquisadores: {str_pesquisadores}{trecho_responsavel}. "
                f"E atualmente o projeto encontra-se {str_situacao}. "
                f"Esse projeto pode ser descrito como: {desc}"
            )

            meta = base_metadata.copy()
            meta.update({
                "tipo": "projeto",
                "titulo": nome,
                "ano_inicio": int(ano_inicio) if ano_inicio.isdigit() else 0,
                "ano_fim": int(ano_fim) if ano_fim.isdigit() else 0,
                "situacao": str_situacao
            })

            docs.append(Document(page_content=content, metadata=meta))

        return docs


    def _get_artigos(self):
        docs = []
        base_metadata = self.researcher_info.copy()

        for artigo in self.root.findall('.//ARTIGO-PUBLICADO'):
            basicos = artigo.find('DADOS-BASICOS-DO-ARTIGO')
            detalhes = artigo.find('DETALHAMENTO-DO-ARTIGO')
            
            if basicos is None or detalhes is None: 
                continue

            autores = []
            for autor in artigo.findall('.//AUTORES'):
                nome = autor.attrib.get('NOME-COMPLETO-DO-AUTOR')
                if nome: 
                    autores.append(f'\'{nome}\'')

            areas_conhecimento = set()
            for areas in artigo.findall('.//AREAS-DO-CONHECIMENTO'):
                for i in range(1, 4):
                    area_tag = areas.find(f'.//AREA-DO-CONHECIMENTO-{i}')
                    if area_tag is not None:
                        nome_area = area_tag.attrib.get('NOME-DA-AREA-DO-CONHECIMENTO')
                        sub_area = area_tag.attrib.get('NOME-DA-SUB-AREA-DO-CONHECIMENTO')
                        especialidade = area_tag.attrib.get('NOME-DA-ESPECIALIDADE')
                        nome_grande = area_tag.attrib.get('NOME-GRANDE-AREA-DO-CONHECIMENTO')
                        
                        if nome_area: areas_conhecimento.add(nome_area)
                        if sub_area: areas_conhecimento.add(sub_area)
                        if especialidade: areas_conhecimento.add(especialidade)
                        if nome_grande: areas_conhecimento.add(nome_grande)

            areas_conhecimento_list = list(areas_conhecimento)

            natureza = basicos.attrib.get('NATUREZA', '').strip()
            titulo = basicos.attrib.get('TITULO-DO-ARTIGO', '').strip()
            ano = basicos.attrib.get('ANO-DO-ARTIGO', '').strip()
            pais = basicos.attrib.get('PAIS-DE-PUBLICACAO', '').strip()
            idioma = basicos.attrib.get('IDIOMA', '').strip()
            meio_divulgacao = basicos.attrib.get('MEIO-DE-DIVULGACAO', '').strip()
            
            titulo_revista = detalhes.attrib.get('TITULO-DO-PERIODICO-OU-REVISTA', '').strip()

            frase_publicacao = []
            if titulo_revista: frase_publicacao.append(f"na revista/periódico '{titulo_revista}'")
            if ano: frase_publicacao.append(f"em {ano}")
            if pais: frase_publicacao.append(f"no país {pais}")
            if idioma: frase_publicacao.append(f"no idioma {idioma}")

            texto_pub = f" foi publicado {' '.join(frase_publicacao)}" if frase_publicacao else " foi publicado"

            frase_caracteristicas = []
            if natureza: frase_caracteristicas.append(f"encontra-se {natureza.lower()}")
            if meio_divulgacao: frase_caracteristicas.append(f"foi divulgado no formato {meio_divulgacao.lower()}")

            texto_caract = f", e {' e '.join(frase_caracteristicas)}" if frase_caracteristicas else ""

            summary = f"O artigo '{titulo}'{texto_pub}{texto_caract}.\n\n"

            texto_autores = f"Os autores desse artigo são: {', '.join(autores)}.\n\n" if autores else ""
            texto_conhecimento = f"Esse artigo está relacionado às seguintes áreas de conhecimento: {', '.join(areas_conhecimento_list)}.\n\n" if areas_conhecimento_list else ""

            content = summary + texto_autores + texto_conhecimento

            meta = base_metadata.copy()
            meta.update({
                "tipo": "artigo",
                "titulo": titulo,
                "ano": int(ano) if ano.isdigit() else 0,
            })
            docs.append(Document(page_content=content, metadata=meta))

        return docs
        

    def _get_orientacoes_mestrado(self, orientacao):
        docs = []
        base_metadata = self.researcher_info.copy()

        for orientacao_mestrado in orientacao.findall('.//ORIENTACOES-CONCLUIDAS-PARA-MESTRADO'):
            dados_basicos = orientacao_mestrado.find('DADOS-BASICOS-DE-ORIENTACOES-CONCLUIDAS-PARA-MESTRADO')
            if dados_basicos is None:
                continue

            titulo = dados_basicos.attrib.get('TITULO', '').strip()
            if not titulo:
                continue

            natureza = dados_basicos.attrib.get('NATUREZA', '').strip()
            ano = dados_basicos.attrib.get('ANO', '').strip()
            pais = dados_basicos.attrib.get('PAIS', '').strip()
            idioma = dados_basicos.attrib.get('IDIOMA', '').strip()

            frase_basica = [f"A orientação de mestrado intitulada '{titulo}'"]
            if natureza: frase_basica.append(f"é um(a) {natureza}")
            if ano: frase_basica.append(f"e foi concluída em {ano}")
            if pais: frase_basica.append(f"no país {pais}")
            if idioma: frase_basica.append(f"no idioma {idioma}")
            
            dados_basicos_str = " ".join(frase_basica) + "."

            detalhamento = orientacao_mestrado.find('DETALHAMENTO-DE-ORIENTACOES-CONCLUIDAS-PARA-MESTRADO')
            detalhamento_str = ""
            if detalhamento is not None:
                tipo_orientacao = detalhamento.attrib.get('TIPO-DE-ORIENTACAO', 'Orientador(a)').strip()
                orientador = base_metadata.get('nome', 'Orientador')
                nome_orientado = detalhamento.attrib.get('NOME-DO-ORIENTADO', '').strip()
                instituicao = detalhamento.attrib.get('NOME-DA-INSTITUICAO', '').strip()
                nome_curso = detalhamento.attrib.get('NOME-DO-CURSO', '').strip()

                if nome_orientado:
                    frase_detalhe = [f"O orientado '{nome_orientado}' teve '{orientador}' como {tipo_orientacao.lower()}"]
                    if instituicao: frase_detalhe.append(f"na instituição '{instituicao}'")
                    if nome_curso: frase_detalhe.append(f"no curso '{nome_curso}'")
                    detalhamento_str = " ".join(frase_detalhe) + "."

            palavras_chave = orientacao_mestrado.find('PALAVRAS-CHAVE')
            palavras_lista = []
            if palavras_chave is not None:
                for i in range(1, 7):
                    pc = palavras_chave.attrib.get(f'PALAVRA-CHAVE-{i}', '').strip()
                    if pc: palavras_lista.append(pc)
            
            palavras_chave_str = f"As palavras-chave associadas a essa orientação são: {', '.join(palavras_lista)}." if palavras_lista else ""

            setores_atividade = orientacao_mestrado.find('SETORES-DE-ATIVIDADE')
            setores_lista = []
            if setores_atividade is not None:
                for i in range(1, 4):
                    sa = setores_atividade.attrib.get(f'SETOR-DE-ATIVIDADE-{i}', '').strip()
                    if sa: setores_lista.append(sa)
            
            setor_atividade_str = f"Os setores de atividade relacionados a essa orientação são: {', '.join(setores_lista)}." if setores_lista else ""

            areas_lista = []
            areas_conhecimento = orientacao_mestrado.find('AREAS-DO-CONHECIMENTO')
            if areas_conhecimento is not None:
                for i in range(1, 4): 
                    area_tag = areas_conhecimento.find(f'AREA-DO-CONHECIMENTO-{i}')
                    if area_tag is not None:
                        atributos_area = [
                            'NOME-GRANDE-AREA-DO-CONHECIMENTO', 'NOME-DA-AREA-DO-CONHECIMENTO', 
                            'NOME-DA-SUB-AREA-DO-CONHECIMENTO', 'NOME-DA-ESPECIALIDADE'
                        ]
                        for attr in atributos_area:
                            val = area_tag.attrib.get(attr, '').strip()
                            if val and val not in areas_lista:
                                areas_lista.append(val)
            
            areas_conhecimento_str = f"As áreas de conhecimento relacionadas a essa orientação são: {', '.join(areas_lista)}." if areas_lista else ""

            partes_conteudo = [dados_basicos_str, detalhamento_str, palavras_chave_str, setor_atividade_str, areas_conhecimento_str]
            content = "\n\n".join(filter(None, partes_conteudo))

            meta = base_metadata.copy()
            meta.update({
                "tipo": "orientacao",
                "titulo": titulo,
                "ano": int(ano) if ano.isdigit() else 0,
                "subtipo": "mestrado",
                "conteudo": content
            })
            docs.append(Document(page_content=content, metadata=meta))
        
        return docs


    def _get_orientacoes(self):
        docs = []
        base_meta = self.researcher_info.copy()

        for orientacao in self.root.findall('.//ORIENTACOES-CONCLUIDAS'):
            #MESTRADO
            docs.extend(self._get_orientacoes_mestrado(orientacao))

        return docs    

    def _get_atuacao(self):
        return None

    def get_production_docs(self):
        """
        Gera lista de documentos para a coleção 'researchers_data'.
        Inclui Artigos, Projetos e Orientações individualmente.
        """
        docs = []
        base_meta = self.researcher_info.copy()

        #1. Projetos de Pesquisa
        docs.extend(self._get_projetos())

        #2. Artigos Publicados
        docs.extend(self._get_artigos())

        #3. Orientações Concluídas
        docs.extend(self._get_orientacoes())

        return docs