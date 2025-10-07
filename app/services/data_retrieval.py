import requests
import time
import asyncio
from typing import List, Dict, Any, Optional
from xml.etree import ElementTree
from app.utils.config import NCBI_RATE_LIMIT_DELAY, API_TIMEOUT


class PubMedRetriever:
    """
    Retrieves paper metadata and abstracts from PubMed using the NCBI E-Utilities API.
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, api_key: Optional[str] = None, email: str = "bioanalyzer@example.com"):
        """
        Initialize the PubMed retriever with an optional API key.
        """
        self.api_key = api_key
        self.email = email
        self.session = requests.Session()
        # Provide a descriptive user agent per NCBI guidelines
        self.session.headers.update({
            "User-Agent": f"BioAnalyzer/1.0 (contact: {self.email})"
        })

    def _get(self, endpoint: str, params: Dict[str, Any], retries: int = 3) -> Optional[str]:
        """
        Internal helper to handle retries and API rate limits.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        if self.api_key:
            params["api_key"] = self.api_key
        params["email"] = self.email
        params["tool"] = "BioAnalyzer"

        for attempt in range(retries):
            try:
                # Respect inter-request delay to avoid rate limiting
                time.sleep(max(NCBI_RATE_LIMIT_DELAY, 0.0))
                # Use conservative timeouts: 5s to connect, <=10s to read
                per_request_timeout = min(API_TIMEOUT or 30, 10)
                response = self.session.get(
                    url,
                    params=params,
                    timeout=(5, per_request_timeout)
                )
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as e:
                # If rate limited, back off more aggressively
                status = getattr(e.response, "status_code", None) if hasattr(e, "response") else None
                if attempt < retries - 1:
                    backoff = (2 ** attempt) * (1.0 if status != 429 else 2.0)
                    time.sleep(backoff)
                    continue
                raise RuntimeError(f"PubMed request failed: {e}")

    def fetch_paper_metadata(self, pmid: str) -> Dict[str, Any]:
        """
        Fetch paper metadata and abstract by PubMed ID.
        """
        xml_data = self._get("efetch.fcgi", {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml"
        })

        if not xml_data:
            return {}

        try:
            root = ElementTree.fromstring(xml_data)
            article = root.find(".//PubmedArticle/MedlineCitation/Article")
            if article is None:
                return {}

            title = article.findtext("ArticleTitle", default="N/A")
            abstract = " ".join(
                [t.text for t in article.findall(".//AbstractText") if t.text]
            )
            journal = article.findtext("Journal/Title", default="N/A")
            authors = [
                f"{a.findtext('ForeName', default='')} {a.findtext('LastName', default='')}".strip()
                for a in article.findall(".//Author")
                if a.findtext("LastName") is not None
            ]

            metadata = {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "authors": authors,
            }

            # Try to extract a publication date if available
            pub_date = article.findtext("Journal/JournalIssue/PubDate/Year")
            if not pub_date:
                pub_date = article.findtext("ArticleDate/Year")
            if pub_date:
                metadata["publication_date"] = pub_date

            return metadata

        except ElementTree.ParseError:
            pass

        # Fallback: try esummary if efetch parsing failed or returned no article
        try:
            xml_sum = self._get("esummary.fcgi", {
                "db": "pubmed",
                "id": pmid,
                "retmode": "xml"
            })
            if not xml_sum:
                return {}
            root = ElementTree.fromstring(xml_sum)
            doc = root.find(".//DocSum")
            if doc is None:
                return {}
            fields: Dict[str, Any] = {}
            for item in doc.findall("Item"):
                name = item.get("Name") or ""
                if name == "Title":
                    fields["title"] = item.text or ""
                elif name == "FullJournalName":
                    fields["journal"] = item.text or ""
                elif name == "PubDate":
                    fields["publication_date"] = item.text or ""
                elif name == "AuthorList":
                    authors: List[str] = []
                    for a in item.findall("Item"):
                        if a.text:
                            authors.append(a.text)
                    fields["authors"] = authors
            fields["pmid"] = pmid
            # Abstract is not returned by esummary; keep empty string
            fields.setdefault("abstract", "")
            fields.setdefault("authors", [])
            return fields
        except Exception:
            return {}

    def search(self, query: str, max_results: int = 10) -> List[str]:
        """
        Search PubMed for PMIDs given a query.
        """
        xml_data = self._get("esearch.fcgi", {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "xml"
        })

        if not xml_data:
            return []

        try:
            root = ElementTree.fromstring(xml_data)
            return [id_elem.text for id_elem in root.findall(".//Id")]
        except ElementTree.ParseError:
            return []

    async def get_paper_metadata_async(self, pmid: str) -> Dict[str, Any]:
        """
        Async wrapper to fetch paper metadata using a background thread.
        """
        return await asyncio.to_thread(self.fetch_paper_metadata, pmid)

    def get_pmc_fulltext(self, pmid: str) -> str:
        """
        Fetch PMC full text for a given PMID if a linked PMCID exists.
        Returns plain text or an empty string if not available.
        """
        try:
            # Find PMCID linked to PMID
            xml_search = self._get("esearch.fcgi", {
                "db": "pmc",
                "term": f"{pmid}[pmid]",
                "retmode": "xml"
            })
            if not xml_search:
                return ""
            try:
                root = ElementTree.fromstring(xml_search)
                pmc_ids = [id_elem.text for id_elem in root.findall(".//Id") if id_elem.text]
                if not pmc_ids:
                    return ""
                pmcid = pmc_ids[0]
            except ElementTree.ParseError:
                return ""

            # Fetch PMC article XML
            xml_full = self._get("efetch.fcgi", {
                "db": "pmc",
                "id": pmcid,
                "retmode": "xml"
            })
            if not xml_full:
                return ""

            # Extract naive text from <body>
            try:
                root_full = ElementTree.fromstring(xml_full)
                body = root_full.find(".//body")
                if body is None:
                    return ""
                texts: List[str] = []
                for elem in body.iter():
                    if elem.text and elem.text.strip():
                        texts.append(elem.text.strip())
                return " ".join(texts)
            except ElementTree.ParseError:
                return ""
        except Exception:
            return ""

    async def get_pmc_fulltext_async(self, pmid: str) -> str:
        """
        Async wrapper for PMC full text retrieval.
        """
        return await asyncio.to_thread(self.get_pmc_fulltext, pmid)

    async def get_paper_data(self, pmid: str) -> Dict[str, Any]:
        """
        Convenience method: combined metadata and full text.
        """
        metadata = await self.get_paper_metadata_async(pmid)
        full_text = await self.get_pmc_fulltext_async(pmid)
        return {
            "pmid": pmid,
            "title": metadata.get("title", ""),
            "abstract": metadata.get("abstract", ""),
            "journal": metadata.get("journal", ""),
            "authors": metadata.get("authors", []),
            "publication_date": metadata.get("publication_date", ""),
            "full_text": full_text or "",
        }

    async def get_texts_for_analysis_async(self, pmid: str) -> Dict[str, str]:
        """
        Minimal retrieval for analysis: abstract and full_text (and optional title).
        Avoids heavy metadata requirements to reduce failure modes.
        """
        # Run metadata and full-text retrieval in parallel with strict timeouts
        async def fetch_metadata():
            try:
                return await asyncio.wait_for(self.get_paper_metadata_async(pmid), timeout=8)
            except Exception:
                return {}

        async def fetch_fulltext():
            try:
                return await asyncio.wait_for(self.get_pmc_fulltext_async(pmid), timeout=10)
            except Exception:
                return ""

        metadata, full_text = await asyncio.gather(fetch_metadata(), fetch_fulltext())
        abstract = metadata.get("abstract", "") if metadata else ""
        title = metadata.get("title", "") if metadata else ""
        return {
            "title": title,
            "abstract": abstract,
            "full_text": full_text or "",
        }
