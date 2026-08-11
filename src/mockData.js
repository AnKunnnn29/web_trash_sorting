import trashItemsData from './trashItems.json' with { type: 'json' };

export const trashItems = trashItemsData;
export const sortableTrashItems = trashItemsData.filter(item => item.category !== 'other');
