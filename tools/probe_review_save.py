"""Read-only-input review-save smoke. The input is synthetic, not play proof."""
import argparse,json
from pathlib import Path
from runtime_probe import Probe

def main():
    p=argparse.ArgumentParser()
    for n in ('core','rom','save','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--resave-only',action='store_true')
    a=p.parse_args();g=Probe(a.core,a.rom,a.out,a.save)
    def press(b,wait=120):
        g.execute({'op':'frames','count':4,'buttons':[b]})
        g.execute({'op':'frames','count':wait})
    def capture(name):g.execute({'op':'screenshot','name':name+'.png'})
    try:
        for q in json.loads(Path('qa/traces/reload-menu.json').read_text())['inputs']:g.execute(q)
        capture('01-loaded-menu')
        if a.resave_only:
            press('up');press('a');capture('02-save-prompt')
            press('a',1800);capture('03-save-result')
            g.execute({'op':'save_export','name':'resaved.sav'})
            return
        press('down');press('a');capture('02-collection-counts')
        press('up');press('a');capture('03-recipe-first')
        press('up');capture('04-recipe-last')
        press('b');press('b');press('up')
        press('a');press('a');press('a');capture('05-party-selection')
        press('down');press('a');capture('06-available-party')
        # Return to the menu; all screens remain available for manual review.
        g.execute({'op':'dump','address':'0x02001d80','length':0xf00,'name':'live-main.bin'})
        g.execute({'op':'save_export','name':'exported.sav'})
        capture('07-final')
    finally:
        g.execute({'op':'close'});g.lib.retro_unload_game();g.lib.retro_deinit()
    print(json.dumps({'status':'CAPTURED_REQUIRES_VISUAL_REVIEW','out':str(a.out)}))

if __name__=='__main__':main()
