// promo v10 montage football shots: other goals of the same five-brand match (foot8/004.html). OV=pos_fix10.json.
const F='004.html';
const S=(o)=>Object.assign({file:F,warm:20},o);
module.exports=[
 // long-range shot down the middle, chase cam behind the ball
 S({name:'f10_long',t0:4050,t1:4121,n:140,cam:"(()=>{const b=ballSm(t,6);return [[b[0]+5,5,b[2]-15],_lerp(b,[0,3,44],0.35),52]})()"}),
 // high lob into the far goal
 S({name:'f10_lob',t0:7040,t1:7121,n:150,cam:"(()=>{const b=ballSm(t,6);return [[b[0]+12,7,b[2]+16],_lerp(b,[0,3,-44],0.3),55]})()"}),
 // off the side wall and in
 S({name:'f10_wall',t0:1925,t1:1991,n:130,cam:"(()=>{const b=ballSm(t,6);return [[b[0]+6,9,b[2]-18],_lerp(b,[-8,3,44],0.3),55]})()"}),
 // inside the other goal: the ball comes at the camera
 S({name:'f10_net2',t0:6750,t1:6800,n:180,cam:"[_lerp([-2,5,-48.5],[-1.4,4.7,-47.8],_ease2(u)),[8,3,-38],55]"}),
 // a solo run from midfield, high crane
 S({name:'f10_run',t0:3150,t1:3268,n:150,cam:"(()=>{const b=ballSm(t,8);return [[b[0]-14,14,b[2]-22],_lerp(b,[0,2,44],0.2),50]})()"}),
 // aerial ball
 S({name:'f10_air',t0:2420,t1:2491,n:150,cam:"(()=>{const b=ballSm(t,6);return [[b[0]-12,6,b[2]-12],b,50]})()"}),
];
// v10c round 2 (mrwang: fewer Octopath, more football in the montage): the strikes themselves, close on the ball
module.exports.push(
 S({name:'f10_k1',t0:3978,t1:4008,n:100,cam:"(()=>{const b=ballSm(t,3);return [[b[0]+8,3.2,b[2]-3],b,42]})()"}),
 S({name:'f10_k2',t0:7007,t1:7037,n:100,cam:"(()=>{const b=ballSm(t,3);return [[b[0]-8,3.5,b[2]+4],b,42]})()"}),
 S({name:'f10_k3',t0:2425,t1:2455,n:100,cam:"(()=>{const b=ballSm(t,3);return [[b[0]+7,3,b[2]-5],b,42]})()"}),
 S({name:'f10_k4',t0:6699,t1:6729,n:100,cam:"(()=>{const b=ballSm(t,3);return [[b[0]+8,4,b[2]+4],b,42]})()"}),
 S({name:'f10_goal5',t0:9540,t1:9612,n:140,cam:"(()=>{const b=ballSm(t,6);return [[b[0]-6,6,b[2]-15],_lerp(b,[0,3,44],0.35),52]})()"}),
);
