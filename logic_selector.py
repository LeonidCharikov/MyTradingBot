import config
from analyzer import analyze_symbol as analyze_old
from analyzer_new import analyze_new_logic

def get_signal(market_data, logic_type=None):
    # Pokud není specifikováno, vezmi to z configu
    if logic_type is None:
        logic_type = config.ANALYSIS_METHOD
        
    if logic_type == "new":
        return analyze_new_logic(market_data)
    else:
        return analyze_old(market_data)