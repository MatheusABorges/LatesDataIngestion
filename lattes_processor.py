import xml.etree.ElementTree as ET
from langchain_core.documents import Document

class LattesProcessor:
    def __init__(self, xml_path):
        self.xml_path = xml_path
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()
        
        # 1. Extração Global (Contexto do Pesquisador)
        # Isso garante que todos os chunks saibam a quem pertencem
        self.researcher_info = self._extract_global_info()

    def _extract_global_info(self):
        """Pega dados que se repetem em todos os chunks"""
        dados_gerais = self.root.find('DADOS-GERAIS')
        
        # Proteção contra XML mal formado
        if dados_gerais is None:
            return {"nome": "Desconhecido", "id_lattes": "0000"}

        return {
            "nome": dados_gerais.attrib.get('NOME-COMPLETO', 'Desconhecido'),
            "id_lattes": self.root.attrib.get('NUMERO-IDENTIFICADOR', '0000'),
            "atualizacao": self.root.attrib.get('DATA-ATUALIZACAO', ''),
            "source": str(self.xml_path)
        }

    def process_bio(self):
        """Chunk 1: O Perfil/Resumo"""
        dados_gerais = self.root.find('DADOS-GERAIS')
        if dados_gerais is None: return []

        resumo = dados_gerais.find('RESUMO-CV')
        if resumo is None: return []

        texto_resumo = resumo.attrib.get('TEXTO-RESUMO-CV-RH', '')
        
        # Enriquecimento do Texto (Contexto)
        content = (
            f"PERFIL BIOGRÁFICO DO PESQUISADOR {self.researcher_info['nome']}.\n"
            f"RESUMO: {texto_resumo}"
        )

        # Metadados Específicos
        metadata = self.researcher_info.copy()
        metadata.update({
            "tipo": "perfil",
            "ano": int(metadata['atualizacao'][-4:]) if len(metadata['atualizacao']) >= 4 else 0
        })

        return [Document(page_content=content, metadata=metadata)]

    def process_education(self):
        """Chunk 2: Formação Acadêmica (Doutorado, Mestrado, etc)"""
        docs = []
        formacao = self.root.find('DADOS-GERAIS/FORMACAO-ACADEMICA-TITULACAO')
        
        if formacao is None: return docs

        # Mapeando tags para nomes legíveis
        mapa_cursos = {
            'DOUTORADO': 'Doutorado',
            'MESTRADO': 'Mestrado',
            'GRADUACAO': 'Graduação',
            'POS-DOUTORADO': 'Pós-Doutorado'
        }

        for tag, nome_legivel in mapa_cursos.items():
            for curso in formacao.findall(tag):
                instituicao = curso.attrib.get('NOME-INSTITUICAO', 'Instituição não informada')
                curso_nome = curso.attrib.get('NOME-CURSO', '')
                ano_conclusao = curso.attrib.get('ANO-DE-CONCLUSAO', '')
                status = curso.attrib.get('STATUS-DO-CURSO', 'CONCLUIDO')

                # Texto Rico
                content = (
                    f"FORMAÇÃO ACADÊMICA DE {self.researcher_info['nome']}: "
                    f"{nome_legivel} em {curso_nome} realizado na {instituicao}. "
                    f"Ano de conclusão: {ano_conclusao}. Status: {status}."
                )

                meta = self.researcher_info.copy()
                meta.update({
                    "tipo": "formacao",
                    "nivel": nome_legivel,
                    "ano": int(ano_conclusao) if ano_conclusao.isdigit() else 0,
                    "instituicao": instituicao
                })

                docs.append(Document(page_content=content, metadata=meta))
        
        return docs

    def process_articles(self):
        """Chunk 3: Artigos Publicados (Um chunk por artigo)"""
        docs = []
        # Caminho profundo no XML
        artigos = self.root.findall('.//ARTIGO-PUBLICADO')

        for artigo in artigos:
            basicos = artigo.find('DADOS-BASICOS-DO-ARTIGO')
            detalhes = artigo.find('DETALHAMENTO-DO-ARTIGO')

            if basicos is None or detalhes is None: continue

            titulo = basicos.attrib.get('TITULO-DO-ARTIGO', '')
            ano = basicos.attrib.get('ANO-DO-ARTIGO', '0')
            revista = detalhes.attrib.get('TITULO-DO-PERIODICO-OU-REVISTA', '')
            doi = basicos.attrib.get('DOI', '')
            
            # Autores (Opcional, mas útil)
            # autores = [a.attrib.get('NOME-COMPLETO-DO-AUTOR') for a in artigo.findall('AUTORES')]

            content = (
                f"PRODUÇÃO CIENTÍFICA DE {self.researcher_info['nome']}.\n"
                f"TIPO: Artigo de Periódico.\n"
                f"TÍTULO: {titulo}.\n"
                f"PUBLICADO EM: {ano}, na revista {revista}.\n"
                f"DOI: {doi}"
            )

            meta = self.researcher_info.copy()
            meta.update({
                "tipo": "producao",
                "subtipo": "artigo",
                "ano": int(ano) if ano.isdigit() else 0,
                "tem_doi": bool(doi)
            })

            docs.append(Document(page_content=content, metadata=meta))

        return docs

    def get_all_chunks(self):
        """Método Mestre que chama todos os processadores"""
        all_docs = []
        all_docs.extend(self.process_bio())
        all_docs.extend(self.process_education())
        all_docs.extend(self.process_articles())
        # Aqui você adicionaria self.process_projects(), etc.
        return all_docs