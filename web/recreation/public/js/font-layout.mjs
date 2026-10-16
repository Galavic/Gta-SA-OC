// GTA uses 32 x 40 cells, with subfonts in the lower atlas rows.
// Texture IDs are reversed relative to their filenames (Font.cpp Initialise).
export const fontKey = id => id === 0 ? 'fonts/font2' : 'fonts/font1';
export function glyph(character, style = 0) {
  const code=character.normalize('NFD').replace(/[\u0300-\u036f]/g,'').charCodeAt(0);
  let id=code>=32&&code<128?code-32:31;
  if (!style) return id;
  if(style===1){const special={1:208,4:93,7:206,8:94,9:95,14:207,26:154};if(id in special)return special[id];}
  if(id===6)return 10;
  if(id>=16&&id<=25)return id+128;
  if(id===31)return 91;
  if(id>=33&&id<=58)return id+122;
  if(id===62)return 32;
  if(id>=65&&id<=90)return id+90;
  return id;
}
export function glyphRect(character, style=0) {
  const id=glyph(character,style);
  return {id,x:(id%16)*32,y:Math.floor(id/16)*40,width:32,height:id>=192?32:40};
}
