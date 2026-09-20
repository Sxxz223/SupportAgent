import { products, type Choice, type View } from './model';
type Node = {id:string;title:string;description:string;choices:Choice[]};
const option=(id:string,label:string,detail?:string):Choice=>({id,label,detail});
const nodes:Record<string,Node>={
 model:{id:'model',title:'确定产品型号',description:'请选择需要帮助的产品型号。',choices:products.filter(p=>p.category==='charger').map(p=>option(p.product_id,p.display_name,p.model))},
 symptom:{id:'symptom',title:'确认故障现象',description:'连接电脑后，具体出现了什么情况？',choices:[option('none','完全没有充电反应'),option('slow','充电速度很慢'),option('unstable','充电时反复断开')]},
 cable:{id:'cable',title:'测试充电线',description:'换一根确认可用、支持电脑充电的线，重新连接设备。',choices:[option('fixed','更换后恢复正常','缩短路径，进入验证'),option('failed','更换后仍无法充电','进一步排查接口与设备'),option('unavailable','没有备用充电线','换一种方式继续排查')]},
 port:{id:'port',title:'测试其他接口',description:'换到另一个适用的输出接口。如果没有其他适用接口，也可以继续。',choices:[option('fixed','更换接口后恢复'),option('failed','仍然没有反应'),option('unavailable','无法测试其他接口')]},
 cross:{id:'cross',title:'连接其他设备测试',description:'尝试为另一台兼容设备充电，观察是否可以正常供电。',choices:[option('works','其他设备可以充电'),option('failed','其他设备也无法充电'),option('unavailable','没有其他设备可测试')]},
 power:{id:'power',title:'核对供电条件',description:'核对说明书中的接口与供电要求，并暂时断开其他用电设备。',choices:[option('ready','供电条件符合'),option('unsure','不确定是否兼容')]},
 compatibility:{id:'compatibility',title:'核对设备兼容性',description:'对照电脑与充电器说明书，核对接口、功率及线材要求。',choices:[option('ready','已核对，符合要求'),option('unavailable','仍无法确认')]},
 reconnect:{id:'reconnect',title:'重新连接电脑',description:'使用已检查的线材和接口重新连接，观察电脑充电图标。',choices:[option('ready','已重新连接'),option('unavailable','暂时无法完成')]},
 verify:{id:'verify',title:'验证充电状态',description:'等待片刻，确认电脑能够持续稳定充电。',choices:[option('normal','现在可以正常充电'),option('failed','仍然存在问题'),option('unavailable','暂时无法验证')]},
 confirm:{id:'confirm',title:'确认问题解决',description:'步骤完成不等于问题解决。最后的 1%，只能由你确认。',choices:[option('solved','已经解决','结束本次服务'),option('failed','仍然存在问题','继续排查')]},
 diagnostic:{id:'diagnostic',title:'检查剩余故障线索',description:'已保留前面的反馈，无需重复操作。现在还有什么异常？',choices:[option('computer','只有电脑无法充电'),option('all','所有设备都无法充电'),option('unstable','连接仍然反复断开')]},
 service:{id:'service',title:'准备后续服务',description:'问题还没有解决。我们已保留此前的排查结果，可以继续验证。',choices:[option('retry','准备好了，重新验证')]},
};
export type DemoState={route:string[];index:number;added:string[];revision:number;round:number;product?:string;notice:string;complete:boolean};
export const initialDemo=():DemoState=>({route:['model','symptom','cable','power','verify','confirm'],index:0,added:[],revision:0,round:0,notice:'',complete:false});
export function demoView(s:DemoState):View{
 const current=nodes[s.route[s.index]];
 const total=s.route.filter(t=>t!=='confirm').length;
 const done=s.route.slice(0,s.index).filter(t=>t!=='confirm').length;
 return {title:s.complete?'这一次，我们一起解决了。':current.title,description:s.complete?'你已确认设备恢复正常。每一次反馈，都让我们离解决更近。':current.description,eyebrow:s.complete?'由你确认，真正完成':s.added.includes(current.id)?'根据你的反馈新增':'一步一步，一起解决',choices:s.complete?[]:current.choices,
 steps:s.route.map((id,i)=>({id:`${id}-${i}`,title:nodes[id].title,status:s.complete||i<s.index?'done':i===s.index?'current':'pending',added:s.added.includes(id)})),progress:s.complete?100:Math.min(99,Math.floor(done/total*99)),note:s.notice,complete:s.complete,confirm:current.id==='confirm'&&!s.complete,product:s.product};
}
export function advanceDemo(previous:DemoState,value:string):DemoState{
 const s={...previous,route:[...previous.route],added:[...previous.added],notice:''};
 if(s.complete)return s;
 const id=s.route[s.index];
 const insert=(types:string[],note:string)=>{s.route.splice(s.index+1,0,...types);s.added.push(...types);s.revision++;s.notice=note;};
 const remaining=(types:string[])=>{s.route=[...s.route.slice(0,s.index+1),...types];};
 const handoff=()=>{remaining(['service']);s.notice='保留已有反馈，转入后续服务准备。问题仍未解决。';s.revision++;};
 const replan=()=>{s.round++;if(s.round>1)handoff();else{remaining(['diagnostic','verify','confirm']);s.added.push('diagnostic');s.revision++;s.notice='没有结束服务。新增故障线索检查，继续寻找原因。';}};
 if(id==='model')s.product=products.find(p=>p.product_id===value)?.display_name;
 if(id==='cable'){
  if(value==='fixed'){remaining(['verify','confirm']);s.revision++;s.notice='更换线材后恢复，已跳过不必要的检查，直接验证。';}
  else insert(['port','cross'],value==='unavailable'?'没有备用线也能继续，先检查接口和其他设备。':'换线后仍无效，新增接口与其他设备测试。');
 }
 if(id==='port'&&value==='fixed'){remaining(['verify','confirm']);s.revision++;s.notice='接口更换后恢复，缩短后续路径，直接验证。';}
 if(id==='power')insert(value==='unsure'?['compatibility','reconnect']:['reconnect'],'核对供电条件后，重新建立连接并验证实际结果。');
 if(['compatibility','reconnect'].includes(id)&&value==='unavailable')handoff();
 if(id==='verify'){if(value==='failed')replan();if(value==='unavailable')handoff();}
 if(id==='confirm'){if(value==='solved'){s.complete=true;return s;}else replan();}
 if(id==='diagnostic'){if(value==='computer')insert(['compatibility','reconnect'],'补充电脑供电条件核对，再重新验证。');else handoff();}
 if(id==='service')insert(['verify','confirm'],'保留此前记录，重新验证实际充电状态。');
 s.index++;return s;
}
