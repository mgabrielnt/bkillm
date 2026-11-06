"""Keep the chat scrolled to the newest text (Streamlit does not do this by itself)."""
from __future__ import annotations

import streamlit.components.v1 as components

# Skrip di iframe tak terlihat. Dipasang sekali per halaman: pengamat perubahan menggulir ke dasar setiap
# teks bertambah, tetapi hanya selama pengguna berada di dekat dasar (menggulir ke atas = berhenti mengikuti).
_INSTALL = """
const win = window.parent;
const box = win.document.querySelector('[data-testid="stAppScrollToBottomContainer"]')
  || win.document.querySelector('[data-testid="stMain"]') || win.document.querySelector('section.main');
if (box && !win.__bkiFollow) {
  let near = true;
  const dist = () => box.scrollHeight - box.scrollTop - box.clientHeight;
  box.addEventListener('scroll', () => { near = dist() < 150; });
  new MutationObserver(() => { if (near) box.scrollTop = box.scrollHeight; })
    .observe(box, {childList: true, subtree: true, characterData: true});
  win.__bkiFollow = {jump: () => { near = true; box.scrollTop = box.scrollHeight; }};
}
"""


# Pasang pengikut scroll (aman dipanggil di setiap render; hanya terpasang sekali).
def follow_scroll() -> None:
    components.html(f"<script>{_INSTALL}</script>", height=0)


# Lompat ke dasar dan mulai mengikuti teks baru lagi (dipanggil saat pertanyaan dikirim).
def scroll_to_bottom() -> None:
    components.html(f"<script>{_INSTALL} if (win.__bkiFollow) win.__bkiFollow.jump();</script>", height=0)
