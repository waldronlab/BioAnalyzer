import re
from typing import Dict, List
from app.utils.bugsigdb_analyzer import BugSigDBAnalyzer


class BasicFieldExtractor:
    """
    Heuristic fallback extractor for the 6 BugSigDB fields when LLM is unavailable.
    Uses keyword and regex-based extraction and BugSigDBAnalyzer helpers.
    """

    HOST_SPECIES_KEYWORDS = {
        'human': ['human', 'homo sapiens', 'patient', 'participants'],
        'mouse': ['mouse', 'mice', 'murine', 'mus musculus'],
        'rat': ['rat', 'rattus'],
        'zebrafish': ['zebrafish', 'danio rerio'],
        'fly': ['drosophila', 'fruit fly'],
    }

    TAXA_LEVEL_KEYWORDS = ['phylum', 'class', 'order', 'family', 'genus', 'species']

    SAMPLE_SIZE_REGEX = [
        r"n\s*=\s*(\d{2,4})",
        r"sample[s]?\s*(size|count)?\s*(of|=)?\s*(\d{2,4})",
        r"participant[s]?\s*(\d{2,4})",
        r"(\d{2,4})\s*(sample[s]?|participant[s]?)",
    ]

    def __init__(self):
        self.analyzer = BugSigDBAnalyzer()

    def extract(self, text: str) -> Dict:
        t = (text or '').lower()
        fields: Dict[str, Dict] = {}

        # Host species
        host_value = None
        for sp, kws in self.HOST_SPECIES_KEYWORDS.items():
            if any(k in t for k in kws):
                host_value = sp
                break
        fields['host_species'] = self._mk_field(host_value)

        # Body site and condition via analyzer dictionaries
        analysis = self.analyzer.analyze_paper(t)
        body_site_value = analysis.get('body_sites', [None])[0] if analysis.get('body_sites') else None
        fields['body_site'] = self._mk_field(body_site_value)

        condition_value = None
        diseases = analysis.get('disease_categories') or []
        if diseases:
            condition_value = diseases[0]
        fields['condition'] = self._mk_field(condition_value)

        # Sequencing type via analyzer
        seqs = analysis.get('sequencing_type') or []
        seq_value = seqs[0] if seqs else None
        fields['sequencing_type'] = self._mk_field(seq_value)

        # Taxa level keyword search
        taxa_value = None
        for k in self.TAXA_LEVEL_KEYWORDS:
            if k in t:
                taxa_value = k
                break
        fields['taxa_level'] = self._mk_field(taxa_value)

        # Sample size regexes
        sample_value = None
        for rgx in self.SAMPLE_SIZE_REGEX:
            m = re.search(rgx, t)
            if m:
                # last group often has the number
                nums = [g for g in m.groups() if g and g.isdigit()]
                if nums:
                    sample_value = nums[-1]
                    break
        fields['sample_size'] = self._mk_field(sample_value)

        return fields

    def _mk_field(self, value: str):
        if value is None:
            return {
                'status': 'ABSENT',
                'value': None,
                'confidence': 0.0,
                'reason_if_missing': 'Not detected by heuristic fallback',
                'suggestions': None,
            }
        return {
            'status': 'PRESENT',
            'value': value,
            'confidence': 0.6,  # heuristic
            'reason_if_missing': None,
            'suggestions': None,
        }
