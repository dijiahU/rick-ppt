'use client';
import {useLanguage} from './language';
import Sunlight from './sunlight';

const REPO='https://github.com/dijiahU/rick-ppt/raw/main/examples/';
/** `at` hangs a print on the wide wall: left, top and width in percent of the wall, then its lean in degrees. `fan` is the side its inner pages spread to. */
type Deck={slug:string;zh:string;en:string;kindZh:string;kindEn:string;pages:number;portrait?:boolean;file?:string;at:[number,number,number,number];fan?:-1};
const decks:Deck[]=[
 {slug:'3d-printing-liquid-metal',zh:'3D 打印液态金属电子皮肤',en:'3D-printed liquid-metal e-skin',kindZh:'学术汇报 · 英文',kindEn:'Research talk',pages:15,at:[1,3.5,30,-1.6]},
 {slug:'silk-road',zh:'丝绸之路',en:'The Silk Road',kindZh:'历史课件',kindEn:'History lesson',pages:5,at:[35,0,24,1.4]},
 {slug:'night-flight-jazz',zh:'夜航爵士',en:'Night Shift Jazz',kindZh:'原创海报',kindEn:'Original poster',pages:1,portrait:true,at:[62.5,1.5,14,-2.2]},
 {slug:'slay-the-spire-2',zh:'杀戮尖塔 2',en:'Slay the Spire 2',kindZh:'游戏宣发',kindEn:'Game promotion',pages:24,at:[78.5,4,20.5,1.8],fan:-1},
 {slug:'montreux-jazz-festival',zh:'蒙特勒音乐节',en:'Montreux Jazz Festival',kindZh:'海报复刻',kindEn:'Poster recreation',pages:1,portrait:true,at:[3,39,13,2.4]},
 {slug:'van-gogh-starry-night',zh:'梵高《星空》',en:'Van Gogh, The Starry Night',kindZh:'艺术赏析',kindEn:'Art appreciation',pages:10,at:[19.5,36,27,-1.2]},
 {slug:'buoyancy-lesson',zh:'浮力',en:'Buoyancy',kindZh:'初二物理课件',kindEn:'Physics lesson, grade 8',pages:5,at:[50,40,22,1.6]},
 {slug:'anc-headphones-launch',zh:'降噪耳机发布',en:'Noise-cancelling headphones launch',kindZh:'发布会大屏',kindEn:'Launch event screen',pages:6,at:[75,35.5,24,-1.8],fan:-1},
 {slug:'seed-pitch-deck',file:'/examples/seed-pitch-deck.pptx',zh:'餐厅备料预测 · 种子轮路演',en:'Restaurant prep forecasting, seed round',kindZh:'融资路演 · 英文',kindEn:'Pitch deck',pages:10,at:[13,70,26,1.2]},
 {slug:'specialty-coffee-brand',zh:'精品咖啡豆',en:'Specialty coffee beans',kindZh:'品牌介绍',kindEn:'Brand introduction',pages:8,at:[58,71,22,-1.4],fan:-1},
];
/** A glossy print catches the room light as the pointer crosses it. */
function sheen(event:React.PointerEvent<HTMLAnchorElement>){
 if(event.pointerType==='touch')return;
 const print=event.currentTarget,box=print.getBoundingClientRect();
 print.style.setProperty('--gx',`${((event.clientX-box.left)/box.width*100).toFixed(1)}%`);
 print.style.setProperty('--gy',`${((event.clientY-box.top)/box.height*100).toFixed(1)}%`);
}
/** Example decks, taped to the wall. Each downloads as the file that was delivered. */
export default function ExampleDecks(){
 const {locale}=useLanguage(),zh=locale==='zh-CN';
 return <section className="example-decks wall" id="examples" aria-labelledby="example-decks-title">
  <Sunlight/>
  <div className="wall-head">
   <h2 id="example-decks-title">{zh?'看几个例子':'A few examples'}</h2>
   <p>{zh?'下载任意一份，在 PowerPoint 或 WPS 里打开：文字、图形和图表都是可以直接修改的原生对象。':'Download any of them and open it in PowerPoint or WPS. The text, shapes and charts are native objects you can keep editing.'}</p>
  </div>
  <ul className="wall-prints">
   {decks.map(d=><li key={d.slug} className={d.portrait?'is-portrait':d.pages>1?'is-stack':undefined} style={{'--x':`${d.at[0]}%`,'--y':`${d.at[1]}%`,'--w':`${d.at[2]}%`,'--lean':`${d.at[3]}deg`,'--fan':d.fan??1} as React.CSSProperties}>
    {/* The next two slides lie under the cover and spread out when the print is pointed at. */}
    {d.pages>1&&[3,2].map(n=><span key={n} className={`print-sheet sheet-${n}`} aria-hidden="true"><img src={`/examples/${d.slug}-p${n}.jpg`} alt="" loading="lazy"/></span>)}
    <a href={d.file??`${REPO}${d.slug}.pptx`} download={d.file?true:undefined} className="example-deck" onPointerMove={sheen}>
     <span className="print-image"><img src={`/examples/${d.slug}-cover.jpg`} alt={zh?`${d.zh}，封面`:`${d.en}, cover slide`} loading="lazy"/></span>
     <span className="example-deck-title">{zh?d.zh:d.en}</span>
     <span className="example-deck-meta">{zh?`${d.kindZh}，${d.pages} 页`:`${d.kindEn}, ${d.pages} ${d.pages===1?'slide':'slides'}`}</span>
     <span className="example-deck-get">{zh?'下载 PPTX':'Download PPTX'}<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 4v11M7 11l5 5 5-5M5 20h14"/></svg></span>
    </a>
   </li>)}
  </ul>
 </section>;
}
