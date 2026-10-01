"""Small aiohttp backend for AquaVibe Chess/UNO Mini Apps.
Disabled by default; enable with AQUA_WEBAPP_ENABLED=true and expose AQUA_MINIAPP_URL.
"""
from __future__ import annotations
import json, random, time, hashlib, hmac, urllib.parse
from pathlib import Path
from aiohttp import web
import config
from AquaVibe.core.mongo import mongodb

CH = mongodb.aqua_chess
UNO = mongodb.aqua_uno
ROOT = Path(__file__).resolve().parent / "webapp"
_runner = None
_site = None

def _web_user(request):
    raw=request.headers.get("X-Telegram-Init-Data", "")
    if not raw: return 0
    try:
        data=dict(urllib.parse.parse_qsl(raw,keep_blank_values=True)); given=data.pop("hash","")
        check="\n".join(f"{k}={data[k]}" for k in sorted(data))
        secret=hmac.new(b"WebAppData",config.BOT_TOKEN.encode(),hashlib.sha256).digest()
        expected=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,given): return 0
        user=json.loads(data.get("user","{}")); return int(user.get("id",0))
    except Exception: return 0

async def health(_): return web.json_response({"ok": True, "service": "AquaVibe Mini Apps"})

async def index(request):
    kind=request.match_info.get("kind","home")
    return web.FileResponse(ROOT / "index.html")

async def chess_state(request):
    gid=request.match_info["game_id"]
    d=await CH.find_one({"type":"game","game_id":gid})
    if not d: return web.json_response({"error":"game_not_found"},status=404)
    try:
        import chess
        board=chess.Board() if d.get("fen") in (None,"startpos") else chess.Board(d["fen"])
        white_clock=float(d.get("white_clock", d.get("base_seconds", 0)))
        black_clock=float(d.get("black_clock", d.get("base_seconds", 0)))
        if d.get("status") == "active" and d.get("base_seconds", 0) and d.get("turn_started_at"):
            elapsed=max(0.0, time.time()-float(d["turn_started_at"]))
            if board.turn: white_clock=max(0.0, white_clock-elapsed)
            else: black_clock=max(0.0, black_clock-elapsed)
        return web.json_response({"game_id":gid,"fen":board.fen(),"turn":"white" if board.turn else "black","legal_moves":[m.uci() for m in board.legal_moves],"status":d.get("status"),"white":d.get("white"),"black":d.get("black"),"mode":d.get("mode","standard"),"time_control":d.get("time_control","10+0"),"white_clock":round(white_clock,1),"black_clock":round(black_clock,1)})
    except Exception as e: return web.json_response({"error":str(e)},status=500)

async def chess_move(request):
    body=await request.json(); gid=request.match_info["game_id"]; uid=_web_user(request); move=body.get("move","")
    d=await CH.find_one({"type":"game","game_id":gid,"status":"active"})
    if not d: return web.json_response({"error":"game_not_active"},status=404)
    if uid not in {int(d.get("white",0)),int(d.get("black",0))}: return web.json_response({"error":"not_player"},status=403)
    import chess
    board=chess.Board() if d.get("fen") in (None,"startpos") else chess.Board(d["fen"])
    side=d["white"] if board.turn else d["black"]
    if int(side)!=uid: return web.json_response({"error":"not_your_turn"},status=409)
    # Apply elapsed time to the side whose clock was running.
    now=time.time(); base=float(d.get("base_seconds",0)); increment=float(d.get("increment",0));
    white_clock=float(d.get("white_clock",base)); black_clock=float(d.get("black_clock",base));
    if base and d.get("turn_started_at"):
        elapsed=max(0.0, now-float(d["turn_started_at"]))
        if board.turn:
            white_clock=max(0.0, white_clock-elapsed)
            if white_clock <= 0:
                d["status"]="finished"; d["winner"]=d["black"]
        else:
            black_clock=max(0.0, black_clock-elapsed)
            if black_clock <= 0:
                d["status"]="finished"; d["winner"]=d["white"]
        if d.get("status")=="finished":
            await CH.update_one({"type":"game","game_id":gid},{"$set":{"status":"finished","winner":d["winner"],"white_clock":white_clock,"black_clock":black_clock,"updated_at":now}})
            await _finish_chess(d, board)
            return await chess_state(request)
    try: mv=chess.Move.from_uci(move)
    except Exception: return web.json_response({"error":"invalid_move"},status=400)
    if mv not in board.legal_moves: return web.json_response({"error":"illegal_move"},status=400)
    board.push(mv)
    if base:
        if not board.turn: white_clock += increment
        else: black_clock += increment
    status="finished" if board.is_game_over() else "active"
    update={"fen":board.fen(),"status":status,"updated_at":now,"white_clock":white_clock,"black_clock":black_clock,"turn_started_at":now}
    await CH.update_one({"type":"game","game_id":gid},{"$set":update,"$push":{"moves":move}})
    if status=="finished": await _finish_chess(d, board)
    return await chess_state(request)

async def _finish_chess(game, board):
    from AquaVibe.utils.chess_rating import apply_result
    if board.is_checkmate(): winner=game["white"] if board.turn==False else game["black"]
    else: winner=game.get("winner")
    await apply_result(game.get("chat_id",0), game["white"], game["black"], winner)

# Lightweight UNO state API. Card format: color:value, wild cards use wild:*
def _deck():
    colors=["red","green","blue","yellow"]; vals=[str(i) for i in range(10)]+["skip","reverse","draw2"]
    d=[]
    for c in colors:
        for v in vals: d.append(f"{c}:{v}")
        for v in vals[1:]: d.append(f"{c}:{v}")
    d += ["wild:*","wild:draw4"]*4; random.shuffle(d); return d
async def uno_state(request):
    gid=request.match_info["game_id"]; d=await UNO.find_one({"type":"game","game_id":gid})
    if not d: return web.json_response({"error":"game_not_found"},status=404)
    return web.json_response({k:d.get(k) for k in ["game_id","players","turn","top","status"]})
async def uno_create(request):
    body=await request.json(); gid=body.get("game_id"); uid=int(body.get("user_id",0))
    lobby=await UNO.find_one({"game_id":gid,"status":"lobby"})
    if not lobby: return web.json_response({"error":"lobby_not_found"},status=404)
    players=list(lobby.get("players",[]))
    if uid not in players: players.append(uid)
    if len(players)<2:
        await UNO.update_one({"game_id":gid},{"$set":{"players":players}}); return web.json_response({"status":"waiting","players":players})
    deck=_deck(); hands={str(p):[deck.pop() for _ in range(7)] for p in players}; top=deck.pop()
    game={"type":"game","game_id":gid,"chat_id":lobby.get("chat_id",0),"players":players[:10],"hands":hands,"deck":deck,"top":top,"turn":0,"status":"active","created_at":time.time()}
    await UNO.replace_one({"game_id":gid},game,upsert=True)
    return web.json_response({"status":"active","players":players,"top":top,"turn":0})
async def uno_play(request):
    body=await request.json(); gid=request.match_info["game_id"]; uid=_web_user(request); card=body.get("card")
    d=await UNO.find_one({"type":"game","game_id":gid,"status":"active"})
    if not d: return web.json_response({"error":"game_not_active"},status=404)
    players=d["players"]; idx=players.index(uid) if uid in players else -1
    if idx<0 or idx!=int(d.get("turn",0)): return web.json_response({"error":"not_your_turn"},status=409)
    hand=list(d["hands"].get(str(uid),[]))
    if card not in hand: return web.json_response({"error":"card_not_in_hand"},status=400)
    top=d.get("top",""); tc,tv=top.split(":",1)
    cc,cv=card.split(":",1)
    if cc!="wild" and cc!=tc and cv!=tv: return web.json_response({"error":"card_not_playable"},status=400)
    hand.remove(card); d["hands"][str(uid)]=hand; d["top"]=card; d["turn"]=(idx+1)%len(players)
    if not hand:
        d["status"]="finished"; d["winner"]=uid
        from AquaVibe.plugins.social.ai_social import _wallet
        await _wallet(d.get("chat_id",0), uid)
        await mongodb.aqua_economy.update_one({"chat_id":d.get("chat_id",0),"user_id":uid},{"$inc":{"balance":5000}})
    await UNO.replace_one({"game_id":gid},d)
    return await uno_state(request)

async def start_webapp():
    global _runner,_site
    if not config.AQUA_WEBAPP_ENABLED: return None
    app=web.Application()
    app.router.add_get('/health',health)
    app.router.add_get('/',index); app.router.add_get('/lobby/{kind:chess|uno}',index); app.router.add_get('/{kind:chess|uno}/{game_id}',index)
    app.router.add_get('/api/chess/{game_id}',chess_state); app.router.add_post('/api/chess/{game_id}/move',chess_move)
    app.router.add_post('/api/uno/{game_id}/join',uno_create); app.router.add_get('/api/uno/{game_id}',uno_state); app.router.add_post('/api/uno/{game_id}/play',uno_play)
    _runner=web.AppRunner(app); await _runner.setup(); _site=web.TCPSite(_runner,config.AQUA_WEBAPP_HOST,config.AQUA_WEBAPP_PORT); await _site.start(); return _runner
async def stop_webapp():
    global _runner
    if _runner: await _runner.cleanup(); _runner=None
