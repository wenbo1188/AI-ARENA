// promo v8 football shots on the five-brand copy (foot8/004.html, made by make_foot8.py). Goal at tick G.
const G=5934,F='004.html';
module.exports=[
 // reveal: dolly toward the green goal, four mascot holograms flanking it, robots charging in
 {name:'f8_holo',file:F,t0:5756,t1:5796,n:120,warm:20,cam:"[_lerp([3,1.4,-6],[-1,2.4,-15],_ease2(u)),_lerp([0,6,-46],[-4,5.5,-46],_ease2(u)),60]"},
 // the strike: a nitro jump hits the ball toward the right wall
 {name:'f8_strike',file:F,t0:5786,t1:5830,n:180,warm:20,cam:"(()=>{const b=ballSm(t,6);return [_lerp([1,1.6,-30],[-1,2.4,-24],_ease2(u)),b,46]})()"},
 // the bank shot, following the ball off the wall to the goal (as v7's fo_goal)
 {name:'f8_goal',file:F,t0:G-100,t1:G+4,n:173,warm:20,cam:"(()=>{const b=ballSm(t,10);return [[b[0]+12,9,b[2]-20],_lerp(b,[-5,3,40],0.25),50]})()"},
 // inside the goal: the ball rolls in past the post toward the camera
 {name:'f8_net',file:F,t0:5900,t1:5956,n:200,warm:20,cam:"[_lerp([2,5,48.5],[1.4,4.7,47.8],_ease2(u)),[-8,3,38],55]"},
];
