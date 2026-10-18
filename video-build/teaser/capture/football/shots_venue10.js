// v10c venue shots (mrwang: football can include shots of the stadium itself, with artful camera moves),
// five-brand copy foot8/004.html
const F='004.html';
const S=(o)=>Object.assign({file:F,warm:20},o);
module.exports=[
 // low-angle push up toward the hologram mascots by the far goal, floodlights behind
 S({name:'f10_holo2',t0:5000,t1:5060,n:120,cam:"[_lerp([-33,1.0,-32],[-28.5,1.5,-38.5],_ease2(u)),_lerp([-23,7,-46.5],[-24.5,8.5,-46.5],_ease2(u)),40]"}),
 // from behind the top tier, air dancers sliding past in the foreground, the pitch beyond
 S({name:'f10_dancers',t0:5000,t1:5080,n:120,cam:"[_lerp([54,18,-26],[54,20,6],_ease2(u)),_lerp([28,7,-14],[28,7,12],_ease2(u)),50]"}),
 // descending orbit over the whole arena
 S({name:'f10_fly',t0:5100,t1:5160,n:140,cam:"(()=>{const e=_ease2(u),a=-2.0+1.3*e,r=78-24*e,h=46-22*e;return [[Math.sin(a)*r,h,Math.cos(a)*r],[0,0,0],50]})()"}),
 // ground-level dolly along the LED boards
 S({name:'f10_boards',t0:5000,t1:5060,n:120,cam:"(()=>{const z=-30+36*_ease2(u);return [[22,0.9,z],[31,1.6,z+16],46]})()"}),
];
