from libmproxy import controller
import threading

def concurrent(fn):
    def _concurrent(ctx, msg):

        reply = msg.reply
        m = msg
        msg.reply = controller.DummyReply()
        if hasattr(reply, "q"):
            msg.reply.q = reply.q

        def run():
            fn(ctx, msg)
            reply()

        threading.Thread(target=run).start()
        
    return _concurrent
