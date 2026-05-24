# gems_system/utils.py
import json

def get_exhaustion_status(row):
    """
    Versão unificada – usa o mesmo parsing robusto do app.py.
    """
    try:
        mc = float(row.get('market_cap', 0))
        analysis_raw = row.get('timeframe_analysis', '{}')
        if isinstance(analysis_raw, str):
            try:
                analysis = json.loads(analysis_raw.replace("'", '"'))
            except json.JSONDecodeError:
                try:
                    analysis = eval(analysis_raw)
                except:
                    analysis = {}
        elif isinstance(analysis_raw, dict):
            analysis = analysis_raw
        else:
            analysis = {}
        trend = analysis.get('acceleration', {}).get('trend', 'stable')
        if mc > 35_000_000 and trend == 'decelerating':
            return "⚠️ ESTICADA"
        elif trend == 'accelerating':
            return "🚀 ACELERANDO"
        elif trend == 'decelerating':
            return "📉 DESACELERANDO"
        return "➡️ ESTÁVEL"
    except:
        return "—"