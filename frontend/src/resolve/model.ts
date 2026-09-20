import catalog from '../../../products/catalog.json';
export const products = catalog;
export type Step = { id: string; title: string; status: 'done' | 'current' | 'pending'; added?: boolean };
export type Choice = { id: string; label: string; detail?: string; message?: string };
export type View = { title: string; description: string; eyebrow: string; choices: Choice[]; steps: Step[]; progress: number | null; note?: string; complete?: boolean; confirm?: boolean; product?: string };

export const liveStages = [
  ['identify_user','确认联系信息'], ['verify_identity','核验购买身份'],
  ['identify_product','确定产品型号'], ['understand_issue','确认故障现象'],
  ['diagnose','一起排查问题'], ['resolved','确认解决结果'],
] as const;
// Backend stage is authoritative. Suggestions are input shortcuts, not diagnoses.
export function liveView(stage: string, confirmed: boolean): View {
  const index = liveStages.findIndex(([id])=>id===stage);
  const text: Record<string,[string,string,Choice[]]> = {
    identify_user:['先认识你，再开始解决。','请告诉我购买时填写的姓名。随后会核对订单号或手机号后四位。',[{id:'help',label:'需要准备哪些信息？',message:'我想咨询售后，需要先准备哪些信息？'}]],
    verify_identity:['核验购买信息。','请按照助手提示，输入订单号或手机号后四位。无需提供完整手机号。',[]],
    identify_product:['选择本次需要帮助的产品。','请选择对应的产品和型号。',products.map(p=>({id:p.product_id,label:p.display_name,detail:p.model,message:`我需要咨询的产品是 ${p.display_name}，型号 ${p.model}。`}))],
    understand_issue:['具体遇到了什么情况？','选择最接近的现象，或在下方补充。',[{id:'none',label:'无法正常充电',message:'设备无法正常充电。'},{id:'slow',label:'充电速度很慢',message:'设备充电速度很慢。'},{id:'other',label:'其他问题',message:'我遇到其他问题，请引导我描述。'}]],
    diagnose:['一起完成当前排查。','按助手给出的操作尝试后，反馈实际结果。',[{id:'done',label:'已完成，问题仍存在',message:'我已经完成你建议的操作，但问题仍然存在，请继续排查。'},{id:'cannot',label:'暂时无法完成操作',message:'我暂时无法完成这个操作，请提供其他处理方式。'},{id:'normal',label:'现在恢复正常了',message:'我已按建议操作，现在设备恢复正常了。'}]],
    resolved:['问题是否真正解决，由你确认。','请确认实际使用结果，再结束本次服务。',[{id:'confirm',label:'已经解决',detail:'结束本次服务',message:'我确认问题已经解决，可以结束本次服务。'},{id:'unresolved',label:'仍然存在问题',detail:'继续排查',message:'问题仍然存在，请不要结束服务，继续帮助我排查。'}]],
  };
  const [title,description,choices]=text[stage] ?? ['继续描述你的情况。','助手正在处理新的服务阶段，请根据回复继续。',[]];
  return {title:confirmed?'这一次，我们一起解决了。':title,description,eyebrow:confirmed?'由你确认，真正完成':'当前任务',choices:confirmed?[]:choices,
    steps:liveStages.map(([id,title],i)=>({id,title,status:confirmed?'done':i<index?'done':i===index?'current':'pending'})),
    progress:confirmed?100:stage==='resolved'?99:null,complete:confirmed,confirm:stage==='resolved'&&!confirmed,
    note:index<0?`已收到新的服务阶段，保留助手回复继续处理。`:undefined};
}
