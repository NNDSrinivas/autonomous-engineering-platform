export enum IntentType {
    ReviewWorkingTree = 'ReviewWorkingTree',
    Unknown = 'Unknown'
}

export interface Intent {
    type: IntentType;
    confidence: number;
}
